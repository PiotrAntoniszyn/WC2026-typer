"""
Flask CLI command: flask init-tournament

Imports WC2026 teams and matches into the database.

Usage:
    flask init-tournament --source api
    flask init-tournament --source json --file data/wc2026.json
    flask init-tournament --source json --file data/wc2026.json --clear
"""
import json
import logging
from datetime import datetime, timezone

import click
from flask.cli import with_appcontext

from app.api.client import PHASE_MAP, get_client
from app.models import Match, PhaseEnum, ResultSourceEnum, Team, db

logger = logging.getLogger(__name__)


@click.command("init-tournament")
@click.option(
    "--source",
    default="api",
    type=click.Choice(["api", "json"]),
    show_default=True,
    help="Data source.",
)
@click.option(
    "--file",
    "json_file",
    default=None,
    type=click.Path(exists=True),
    help="Path to JSON file (required when --source=json).",
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Delete existing teams and matches before importing.",
)
@with_appcontext
def init_tournament_cmd(source: str, json_file: str | None, clear: bool) -> None:
    """Import WC2026 teams and matches into the database."""
    if clear:
        click.confirm("This will delete all existing teams and matches. Continue?", abort=True)
        Match.query.delete()
        Team.query.delete()
        db.session.commit()
        click.echo("Cleared existing data.")

    if source == "api":
        _import_from_api()
    else:
        if not json_file:
            raise click.UsageError("--file is required when --source=json")
        _import_from_json(json_file)

    click.echo("Tournament initialisation complete.")


def _parse_datetime(dt_str: str) -> datetime:
    """Parse ISO 8601 UTC datetime string from football-data.org."""
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)


def _upsert_teams(api_teams: list[dict]) -> dict[str, Team]:
    """Upsert teams from API data. Returns mapping country_code → Team."""
    team_map: dict[str, Team] = {}
    for t in api_teams:
        code = t.get("tla", "")
        if not code:
            continue
        team = Team.query.filter_by(country_code=code).first()
        if not team:
            team = Team(country_code=code)
            db.session.add(team)
        team.name = t.get("name", code)
        team.flag_url = t.get("crest")
        team_map[code] = team

    db.session.flush()
    return team_map


def _upsert_matches(api_matches: list[dict], team_map: dict[str, Team]) -> int:
    """Upsert matches from API data. Returns count of records affected.

    Knockout matches with TBD teams (null TLA) are stored with a placeholder
    team pair created on the fly so the NOT NULL constraint is satisfied.
    They get updated once real teams are known via a subsequent sync.
    """
    placeholder_team = _get_or_create_placeholder_team()
    count = 0

    for m in api_matches:
        ext_id = m.get("id")
        if ext_id is None:
            continue

        match = Match.query.filter_by(external_id=ext_id).first()
        if not match:
            match = Match(external_id=ext_id)
            db.session.add(match)

        stage = m.get("stage", "GROUP_STAGE")
        phase_value = PHASE_MAP.get(stage, "group")
        match.phase = PhaseEnum(phase_value)

        raw_group = m.get("group") or ""
        match.group_letter = raw_group.replace("GROUP_", "")[:1] or None

        match.match_datetime = _parse_datetime(m["utcDate"])
        match.venue = m.get("venue")

        home_tla = (m.get("homeTeam") or {}).get("tla") or ""
        away_tla = (m.get("awayTeam") or {}).get("tla") or ""

        home_team = team_map.get(home_tla)
        away_team = team_map.get(away_tla)

        # Only overwrite team assignment when we have real data.
        # For TBD knockout slots, keep existing assignment (or use placeholder).
        if home_team:
            match.home_team_id = home_team.id
        elif not match.home_team_id:
            match.home_team_id = placeholder_team.id
            logger.debug("Placeholder home team for match %d (stage: %s)", ext_id, stage)

        if away_team:
            match.away_team_id = away_team.id
        elif not match.away_team_id:
            match.away_team_id = placeholder_team.id
            logger.debug("Placeholder away team for match %d (stage: %s)", ext_id, stage)

        # Import result if already available
        score = m.get("score", {})
        full_time = score.get("fullTime", {})
        if full_time.get("home") is not None and full_time.get("away") is not None:
            match.home_score = full_time["home"]
            match.away_score = full_time["away"]
            match.result_source = ResultSourceEnum.API
            match.is_locked = True

        count += 1

    return count


def _get_or_create_placeholder_team() -> Team:
    """Return a sentinel 'TBD' team used for knockout slots not yet filled."""
    team = Team.query.filter_by(country_code="TBD").first()
    if not team:
        team = Team(country_code="TBD", name="TBD")
        db.session.add(team)
        db.session.flush()
    return team


def _import_from_api() -> None:
    click.echo("Fetching data from football-data.org...")
    with get_client() as client:
        api_teams = client.get_teams()
        api_matches = client.get_matches()

    team_map = _upsert_teams(api_teams)
    count = _upsert_matches(api_matches, team_map)
    db.session.commit()
    click.echo(f"Imported {len(api_teams)} teams and {count} matches from API.")


def _import_from_json(path: str) -> None:
    """
    JSON file format:
    {
      "teams": [ { "tla": "BRA", "name": "Brazil", "crest": "https://..." }, ... ],
      "matches": [ { "id": 1, "stage": "GROUP_STAGE", "group": "GROUP_A",
                     "utcDate": "2026-06-11T20:00:00Z",
                     "homeTeam": {"tla": "BRA"}, "awayTeam": {"tla": "MEX"},
                     "score": {"fullTime": {"home": null, "away": null}} }, ... ]
    }
    """
    click.echo(f"Loading data from {path}...")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    api_teams = data.get("teams", [])
    api_matches = data.get("matches", [])

    team_map = _upsert_teams(api_teams)
    count = _upsert_matches(api_matches, team_map)
    db.session.commit()
    click.echo(f"Imported {len(api_teams)} teams and {count} matches from JSON.")
