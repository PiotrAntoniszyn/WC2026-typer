# WC2026 Typer

A match prediction app for FIFA World Cup 2026, built for a closed group of friends.

Stack: Flask 3 · SQLAlchemy 2 · SQLite (dev) / Supabase PostgreSQL (prod) · APScheduler · Bootstrap 5

> **Status:** in development — WC2026 starts June 2026

---

## Table of Contents

1. [Requirements](#1-requirements)
2. [Local Setup](#2-local-setup)
3. [Environment Variables](#3-environment-variables)
4. [Database](#4-database)
5. [Tournament Data Import](#5-tournament-data-import)
6. [Running Dev Server](#6-running-dev-server)
7. [Tests](#7-tests)
8. [Linting](#8-linting)
9. [VPS Deployment](#9-vps-deployment)
10. [Project Structure](#10-project-structure)
11. [How the Scheduler Works](#11-how-the-scheduler-works)
12. [Troubleshooting](#12-troubleshooting)
13. [Scoring System](#13-scoring-system)
14. [License](#14-license)
15. [Contact](#15-contact)

---

## 1. Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — the only package manager used in this project
- API key from [football-data.org](https://www.football-data.org/) (free tier)
- (prod) Supabase account with a PostgreSQL project

---

## 2. Local Setup

```bash
# Clone the repo and enter the directory
git clone <repo-url>
cd WC2026-typer

# Create virtual environment and install dependencies
uv venv
uv sync

# Copy the example env file and fill in your values
cp .env.example .env
```

Then edit `.env` — see details below.

---

## 3. Environment Variables

All settings go into `.env` in the project root.
`.env.example` contains a complete template.

| Variable | Description | Example |
|---|---|---|
| `FLASK_APP` | Entry point for CLI | `wsgi` |
| `FLASK_ENV` | Application mode (`development` / `production`) | `development` |
| `SECRET_KEY` | Flask session key — **must be random in prod** | `openssl rand -hex 32` |
| `DATABASE_URL` | Database connection string | `sqlite:///wc2026.db` |
| `INVITE_CODE` | Code required during registration | `wc2026` |
| `FOOTBALL_DATA_API_KEY` | football-data.org API key | `abc123...` |
| `LOCK_MINUTES_BEFORE` | Minutes before match when predictions are locked | `60` |
| `ADMIN_EMAIL` | First admin's email (informational) | `you@example.com` |

**Generating `SECRET_KEY` for production:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**`DATABASE_URL` for Supabase:**
```
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```
Copy from Supabase Dashboard → Settings → Database → **Connection pooling → Session mode → URI**.

> Use the **Session pooler** (port 5432), not the Transaction pooler (port 6543) or direct connection.
> Direct connections are blocked by NAT/firewall on many home networks and VPS providers.

SQLAlchemy requires the `postgresql://` prefix — if Supabase provides `postgres://`, the app corrects it automatically.

**Changing `INVITE_CODE` and `LOCK_MINUTES_BEFORE` at runtime:**
These settings can also be edited via the admin panel (`/admin/settings`) without restarting the server.
Values from `.env` are only used on first startup to seed the `app_settings` table.

---

## 4. Database

### Initialization (once per fresh project)

```bash
uv run flask db init       # creates the migrations/ directory
uv run flask db migrate -m "initial schema"
uv run flask db upgrade
```

`migrations/` is part of the repo — do not delete it.

### Day-to-day — after model changes

```bash
uv run flask db migrate -m "description of change"
uv run flask db upgrade
```

### Dev database reset (when things break)

Stop Flask first, then:

```bash
# Linux/Mac
rm instance/wc2026.db

# Windows
del instance\wc2026.db

uv run flask db upgrade
uv run flask init-tournament --source api
```

On startup the app automatically detects missing tables and creates them via `db.create_all()` — this applies to SQLite only. For PostgreSQL always use `flask db upgrade`.

> **Warning:** Always stop the server before deleting `instance/wc2026.db`.
> SQLite on Windows locks the file — deleting it while Flask is running leaves
> an empty database with only `alembic_version`, which causes `no such table` on next startup.

### SQLite — file location

The app always uses the absolute path `instance/wc2026.db` regardless of the working directory.
In production there is no file — the database is Supabase (PostgreSQL).

---

## 5. Tournament Data Import

```bash
# From football-data.org API (requires API key)
uv run flask init-tournament --source api

# From a local JSON file (format described in scripts/init_tournament.py)
uv run flask init-tournament --source json --file data/wc2026.json

# Clear existing data and re-import
uv run flask init-tournament --source api --clear
```

What this command does:
- Fetches 48 teams and 104 matches from the API
- Group stage matches have real teams assigned
- Knockout matches (Round of 32, etc.) get a `TBD` placeholder — updated by the scheduler once results come in

Run after every `flask db upgrade` on a fresh database.

---

## 6. Running Dev Server

```bash
uv run flask run
```

App starts at `http://127.0.0.1:5000`.

The first registered user automatically receives admin privileges.

**Debug mode** is active when `FLASK_ENV=development`. The Werkzeug reloader works normally — APScheduler starts only in the child process (prevents double execution).

---

## 7. Tests

```bash
# All tests
uv run pytest

# Specific file
uv run pytest tests/test_scoring.py -v

# With output visible
uv run pytest -s
```

Tests use an in-memory SQLite database (`sqlite:///:memory:`) — they do not touch `instance/wc2026.db`.
CSRF is disabled in test mode.

---

## 8. Linting

```bash
# Check
uv run ruff check .

# Auto-fix
uv run ruff check --fix .

# Format
uv run ruff format .
```

---

## 9. VPS Deployment

Assumes Ubuntu 22.04, Python 3.12, Nginx, Certbot.

### One-time server setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repo (URL available on the GitHub repository page)
git clone <repo-url> /srv/wc2026-typer
cd /srv/wc2026-typer

# Virtual environment and dependencies
uv venv
uv sync

# Fill in production variables
cp .env.example .env
nano .env   # set FLASK_ENV=production, SECRET_KEY, DATABASE_URL (Supabase), FOOTBALL_DATA_API_KEY
```

### Database initialization (Supabase)

```bash
uv run flask db upgrade
uv run flask init-tournament --source api
```

### Systemd — Gunicorn

Create `/etc/systemd/system/wc2026.service`:

```ini
[Unit]
Description=WC2026 Typer (Gunicorn)
After=network.target

[Service]
User=www-data
WorkingDirectory=/srv/wc2026-typer
EnvironmentFile=/srv/wc2026-typer/.env
ExecStart=/srv/wc2026-typer/.venv/bin/gunicorn \
    --workers 1 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/wc2026/access.log \
    --error-logfile /var/log/wc2026/error.log \
    wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
mkdir -p /var/log/wc2026
systemctl daemon-reload
systemctl enable wc2026
systemctl start wc2026
systemctl status wc2026
```

> **`--workers 1`** — APScheduler runs inside the Gunicorn process.
> Multiple workers = multiple scheduler instances = results pulled multiple times simultaneously.
> Stay with one worker or move the scheduler to a separate process / cron job.

### Nginx

Create `/etc/nginx/sites-available/wc2026`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/wc2026 /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### HTTPS (Certbot)

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

Certbot automatically updates the Nginx config and sets up auto-renewal.

### Deploying a new version

```bash
cd /srv/wc2026-typer
git pull
uv sync                      # if dependencies changed
uv run flask db upgrade      # if there are new migrations
systemctl restart wc2026
```

---

## 10. Project Structure

```
wc2026-typer/
├── app/
│   ├── __init__.py          # create_app factory, blueprint registration
│   ├── models.py            # SQLAlchemy models (Team, Match, Prediction, User, AppSettings)
│   ├── scoring.py           # scoring logic — pure functions, no Flask context
│   ├── scheduler.py         # APScheduler: match locking + result polling
│   ├── auth/                # blueprint /register /login /logout
│   ├── main/                # blueprint / /matches /leaderboard /profile
│   ├── predict/             # blueprint /matches/<id>/predict /champion
│   ├── admin/               # blueprint /admin/* (requires is_admin)
│   ├── api/
│   │   └── client.py        # football-data.org client + sync_results()
│   └── templates/           # Jinja2, Bootstrap 5
├── migrations/              # Alembic — commit to repo
├── scripts/
│   └── init_tournament.py   # flask init-tournament CLI command
├── tests/
│   ├── conftest.py
│   ├── test_scoring.py      # scoring unit tests (no database)
│   └── test_auth.py         # auth smoke tests
├── instance/                # SQLite dev DB — do not commit
├── .env                     # secret variables — do not commit
├── .env.example             # .env template — commit this
├── config.py                # pydantic-settings: Development/Production/TestingSettings
├── pyproject.toml           # dependencies, ruff, pytest config
└── wsgi.py                  # Gunicorn entry point
```

---

## 11. How the Scheduler Works

APScheduler starts automatically with the application (except in test mode).

| Job | Frequency | What it does |
|---|---|---|
| `lock_matches` | every 1 min | Sets `Match.is_locked = True` for matches within the `LOCK_MINUTES_BEFORE` window |
| `pull_results` | every 5 min | Fetches FINISHED results from the API, updates TBD teams in knockout matches, awards points |

The scheduler can also be triggered manually from the admin panel:
- **Sync API** — `/admin/api-sync` — one-off result pull
- **Recalculate** — `/admin/recalculate` — recalculate points for a specific match

---

## 12. Troubleshooting

**`no such table: teams` on `flask init-tournament`**

Alembic thinks the database is up to date, but the tables don't exist (database was deleted manually while the server was running).

```bash
# Check what's in the database
python -c "import sqlite3; c=sqlite3.connect('instance/wc2026.db'); print(c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())"

# If only [(alembic_version,)]:
python -c "import sqlite3; c=sqlite3.connect('instance/wc2026.db'); c.execute('DELETE FROM alembic_version'); c.commit()"
uv run flask db upgrade
uv run flask init-tournament --source api
```

---

**Scheduler starts twice in dev mode**

Werkzeug reloader forks the process. The code in `scheduler.py` checks `WERKZEUG_RUN_MAIN` and starts the scheduler only in the child process. If you see duplicated logs — that's a bug, please report it.

---

**`VIRTUAL_ENV=... does not match` warning from uv**

You have another Python environment activated in the terminal (e.g. a global one). Safe to ignore — `uv run` always uses `.venv` from the project. You can also deactivate the global environment: `deactivate`.

---

**Changing `INVITE_CODE` has no effect after editing `.env`**

The invite code is stored in the `app_settings` table, not read from `.env` on every request. Change it via the admin panel: `/admin/settings`.

---

**`could not translate host name ... supabase.co` on `flask db upgrade`**

Supabase blocks direct connections on many networks. Make sure you are using the **Session pooler**:

1. Go to Supabase Dashboard → Settings → Database → Connection pooling
2. Select **Session mode**
3. Copy the URI and paste it into `DATABASE_URL` in `.env`

Also check whether your Supabase project is paused — free-tier projects pause after a week of inactivity. Resume it manually from the dashboard.

---

**Alembic migration detects too few / too many changes**

Make sure all models are imported before Alembic runs autogenerate. The import in `app/__init__.py` ensures models are loaded when Flask-Migrate runs `env.py`. If you add a new model — import it in `app/models.py`.

---

## 13. Scoring System

Points are awarded automatically after a match result is entered.

| Phase | Exact score | Correct winner / draw |
|---|---|---|
| Group stage | 3 pts | 1 pt |
| Knockout rounds (all) | 5 pts | 2 pts |

**Exact score** = correct number of goals for both teams.  
**Correct winner / draw** = right side wins or correctly predicted draw, without the exact scoreline.

**Champion bonus** — 20 pts for correctly predicting the tournament winner. The prediction window closes with the first match of WC2026.

A user who did not submit a prediction before the lock = 0 pts for that match.

---

## 14. License

Private project — intended for a closed group of users. All rights reserved.

---

## 15. Contact

**Piotr Antoniszyn** — [piotrantoniszyn@outlook.com](mailto:piotrantoniszyn@outlook.com)
