import logging

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup

from app.models import User, db

logger = logging.getLogger(__name__)

login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config=None) -> Flask:
    app = Flask(__name__, template_folder="templates")

    from config import get_config

    cfg = config or get_config()

    app.config["SECRET_KEY"] = cfg.secret_key

    db_uri = cfg.sqlalchemy_database_uri
    # sqlite:///name.db is relative to CWD, which varies by how Flask is launched.
    # Pin it to the instance folder so the path is always deterministic.
    # Skip :memory: and already-absolute paths (sqlite:////...).
    if (
        db_uri.startswith("sqlite:///")
        and not db_uri.startswith("sqlite:////")
        and ":memory:" not in db_uri
    ):
        import os
        db_name = db_uri[len("sqlite:///"):]
        db_uri = "sqlite:///" + os.path.join(app.instance_path, db_name)
        os.makedirs(app.instance_path, exist_ok=True)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DEBUG"] = cfg.debug
    app.config["TESTING"] = cfg.testing
    app.config["WTF_CSRF_ENABLED"] = not cfg.testing
    app.config["LOCK_MINUTES_BEFORE"] = cfg.lock_minutes_before

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @app.template_filter("flag_img")
    def flag_img_filter(team, size: str = "sm") -> Markup:
        """Render an <img> or placeholder span for a team flag.

        Usage in templates: {{ match.home_team | flag_img("sm") }}
        Sizes: "sm" = 24x18, "lg" = 48x36
        """
        sizes = {"sm": "width:24px;height:18px", "lg": "width:48px;height:36px"}
        style = sizes.get(size, sizes["sm"])
        if team and team.flag_url:
            return Markup(
                f'<img src="{team.flag_url}" alt="{team.name}"'
                f' style="{style};object-fit:cover" class="flag-icon">'
            )
        name = team.name if team else "TBD"
        return Markup(
            f'<span class="flag-icon d-inline-block bg-secondary rounded-1"'
            f' style="{style}" title="{name}"></span>'
        )

    from app.auth import auth_bp
    from app.main import main_bp
    from app.predict import predict_bp
    from app.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    with app.app_context():
        _ensure_tables_exist()
        _ensure_app_settings(cfg)

    if not cfg.testing:
        from app.scheduler import start_scheduler

        start_scheduler(app)

    from scripts.init_tournament import init_tournament_cmd

    app.cli.add_command(init_tournament_cmd)

    return app


def _ensure_tables_exist() -> None:
    """Create all tables if they don't exist yet (SQLite dev only).

    Alembic manages schema migrations, but on a fresh SQLite file the tables
    may be missing while alembic_version already exists (e.g. after flask db init).
    db.create_all() is a no-op when tables already exist, so it's safe to call always.
    Skipped for non-SQLite databases — use flask db upgrade there.
    """
    from sqlalchemy import inspect

    if not db.engine.url.drivername.startswith("sqlite"):
        return

    try:
        inspector = inspect(db.engine)
        if "matches" not in inspector.get_table_names():
            db.create_all()
            logger.info("Created database tables via db.create_all()")
    except Exception as exc:
        logger.warning("Could not check/create tables: %s", exc)


def _ensure_app_settings(cfg) -> None:
    """Create the single AppSettings row if the table exists but the row doesn't."""
    from sqlalchemy import inspect, text

    from app.models import AppSettings

    inspector = inspect(db.engine)
    if "app_settings" not in inspector.get_table_names():
        # Tables haven't been created yet (first run before db upgrade)
        return

    if db.session.get(AppSettings, 1) is None:
        settings = AppSettings(
            id=1,
            invite_code=cfg.invite_code,
            lock_minutes_before=cfg.lock_minutes_before,
        )
        db.session.add(settings)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
