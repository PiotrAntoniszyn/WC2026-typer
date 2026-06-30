import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

COMPETITION = "2000"
BASE_URL = "https://api.football-data.org/v4"

PHASE_MAP: dict[str, str] = {
    "GROUP_STAGE": "group",
    "LAST_32": "r32",
    "ROUND_OF_32": "r32",   # keep for any older API responses
    "LAST_16": "r16",
    "ROUND_OF_16": "r16",
    "QUARTER_FINALS": "qf",
    "SEMI_FINALS": "sf",
    "THIRD_PLACE": "third_place",
    "FINAL": "final",
}


class FootballDataClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.Client(
            headers={"X-Auth-Token": api_key},
            timeout=15.0,
        )

    def get_matches(self, status: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        r = self._client.get(f"{BASE_URL}/competitions/{COMPETITION}/matches", params=params)
        r.raise_for_status()
        return r.json()["matches"]

    def get_teams(self) -> list[dict[str, Any]]:
        r = self._client.get(f"{BASE_URL}/competitions/{COMPETITION}/teams")
        r.raise_for_status()
        return r.json()["teams"]

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def get_client() -> FootballDataClient:
    from config import get_config

    cfg = get_config()
    return FootballDataClient(cfg.football_data_api_key)


def clear_manual_results(app) -> int:
    """
    Reset results that were manually entered (result_source == MANUAL) for matches
    that have an external_id and can therefore be re-fetched from the API.
    Nulls out prediction points then fully rebuilds all user totals so the state
    stays consistent regardless of any prior inconsistencies.
    Leaves is_locked intact — the match already happened.
    Returns count of matches cleared.
    """
    from app.models import Match, ResultSourceEnum, db
    from app.scoring import recalculate_all_totals

    with app.app_context():
        manual_matches = Match.query.filter(
            Match.result_source == ResultSourceEnum.MANUAL,
            Match.external_id.isnot(None),
        ).all()

        for match in manual_matches:
            for prediction in match.predictions:
                prediction.points_awarded = None
            match.home_score = None
            match.away_score = None
            match.result_source = None

        if manual_matches:
            recalculate_all_totals()
            logger.info("Cleared %d manual result(s) before API sync", len(manual_matches))

        db.session.commit()
        return len(manual_matches)


def sync_results(app) -> int:
    """
    Pull all matches from API, update DB:
    - Fills in real team assignments for knockout slots that had TBD placeholders.
    - Updates results for FINISHED matches and triggers scoring.
    Returns count of matches whose result changed.
    Must be called with or within app context.
    """
    from app.models import Match, ResultSourceEnum, Team, db
    from app.scoring import score_match

    updated = 0
    try:
        with get_client() as client:
            api_matches = client.get_matches()
    except httpx.HTTPError as exc:
        logger.error("API request failed: %s", exc)
        return 0

    with app.app_context():
        for api_m in api_matches:
            ext_id = api_m.get("id")
            match = Match.query.filter_by(external_id=ext_id).first()
            if match is None:
                continue

            # Update TBD team slots when real teams are now known
            home_tla = (api_m.get("homeTeam") or {}).get("tla") or ""
            away_tla = (api_m.get("awayTeam") or {}).get("tla") or ""

            if home_tla:
                home_team = Team.query.filter_by(country_code=home_tla).first()
                if home_team and match.home_team_id != home_team.id:
                    match.home_team_id = home_team.id

            if away_tla:
                away_team = Team.query.filter_by(country_code=away_tla).first()
                if away_team and match.away_team_id != away_team.id:
                    match.away_team_id = away_team.id

            # Update result — use only the 90-minute score.
            # For ET/PSO matches the API populates `regularTime` with the
            # 90-min score; `fullTime` is the cumulative total across all
            # phases (regular + ET + penalties) and must be ignored.
            score_obj = api_m.get("score", {})
            duration = score_obj.get("duration", "REGULAR")
            time_score = score_obj.get("regularTime") or score_obj.get("fullTime") or {}
            home_score = time_score.get("home")
            away_score = time_score.get("away")
            if home_score is None or away_score is None:
                continue

            if duration != "REGULAR":
                logger.info(
                    "Match %s went to %s — storing 90-min score %s-%s",
                    ext_id, duration, home_score, away_score,
                )

            if match.home_score != home_score or match.away_score != away_score:
                match.home_score = home_score
                match.away_score = away_score
                match.result_source = ResultSourceEnum.API
                match.is_locked = True
                score_match(match)
                updated += 1

        db.session.commit()
        if updated:
            logger.info("Synced %d match results from API", updated)

    return updated
