# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WC2026 Typer is a Flask web app for predicting FIFA World Cup 2026 match scores. Users register with an invite code, submit score predictions before each match locks, and earn points based on accuracy. An admin panel handles result entry, API sync with football-data.org, and settings.

## Commands

All commands use `uv`. Never use `pip` or `python` directly.

```bash
# Dev server
uv run flask run

# Testing
uv run pytest                            # all tests
uv run pytest tests/test_scoring.py -v  # single file

# Linting / formatting
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .

# Database migrations
uv run flask db migrate -m "description"
uv run flask db upgrade

# Seed tournament data (run once after db upgrade)
uv run flask init-tournament --source api
```

## Architecture

**Application factory** — `app/__init__.py:create_app()` wires up all extensions (SQLAlchemy, Flask-Migrate, Flask-Login, CSRF, APScheduler) and registers four blueprints:

| Blueprint | Prefix | Responsibility |
|-----------|--------|----------------|
| `auth` | `/` | Register / login / logout |
| `main` | `/` | Index, match list, leaderboard, profile |
| `predict` | `/` | Score entry and champion pick |
| `admin` | `/admin` | Result entry, API sync, settings, recalculate |

**Scoring** — `app/scoring.py` is pure Python with no Flask context. Group stage: 3 pts exact / 1 pt correct outcome. Knockout: 5 pts exact / 2 pts correct outcome. Champion bonus: 20 pts. `score_match()` applies delta updates on top of previously awarded points so re-scoring is safe.

**Scheduler** — `app/scheduler.py` runs two APScheduler background jobs: `lock_matches` (every 1 min) and `pull_results` (every 5 min). In dev, the `WERKZEUG_RUN_MAIN` guard prevents duplicate job registration from the reloader.

**External API** — `app/api/client.py` wraps football-data.org v4. `sync_results()` fetches FINISHED matches, updates TBD knockout teams, and triggers scoring. Can be called by the scheduler or manually via `/admin/api-sync`.

**Config** — `config.py` uses `pydantic-settings`. Three classes: `DevelopmentSettings`, `ProductionSettings`, `TestingSettings`. Auto-corrects `postgres://` → `postgresql://` for SQLAlchemy 2.x. Settings override: `.env` file → env vars → Pydantic defaults.

**AppSettings model** — Single DB row (id=1) for runtime-editable values (`invite_code`, `lock_minutes_before`). Seeded from `.env` on first startup; edited via admin panel thereafter.

## Database

SQLite for development, Supabase PostgreSQL in production. Alembic migrations are committed — always run `flask db upgrade` after pulling model changes.

Key model notes:
- `Match.phase` uses `PhaseEnum`: `group | r32 | r16 | qf | sf | third_place | final`
- Knockout matches are created with TBD placeholder teams; `sync_results()` fills them in as the tournament progresses.
- `User.total_points` is a cached aggregate; `recalculate_all_totals()` rebuilds it from all `Prediction.points_awarded` values.
- `Prediction` has a unique constraint on `(user_id, match_id)`.

## Testing

Tests use in-memory SQLite and disable CSRF. `conftest.py` provides `app`, `client`, and `runner` fixtures. `test_scoring.py` tests pure scoring functions without a DB; `test_auth.py` covers registration and login flows.

## Production Deployment

Gunicorn via systemd (`wc2026.service`), fronted by Nginx. Deploy with `deploy.sh` (git pull → `uv sync --no-dev` → `flask db upgrade` → `systemctl restart wc2026`). Use `--workers 1` with Gunicorn — APScheduler must not run in multiple worker processes simultaneously.

## Environment Variables

See `.env.example`. Key variables: `SECRET_KEY`, `DATABASE_URL`, `FOOTBALL_DATA_API_KEY`, `INVITE_CODE`, `LOCK_MINUTES_BEFORE`.
