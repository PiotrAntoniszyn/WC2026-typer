import logging
import os
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def lock_expired_matches(app) -> None:
    """Mark matches as locked when they enter the pre-kick-off lock window."""
    from app.models import Match, db

    now = datetime.now(timezone.utc)
    with app.app_context():
        lock_minutes = app.config.get("LOCK_MINUTES_BEFORE", 60)
        cutoff = now + timedelta(minutes=lock_minutes)
        matches = Match.query.filter(
            Match.is_locked == False,  # noqa: E712
            Match.match_datetime <= cutoff,
        ).all()
        for m in matches:
            m.is_locked = True
        if matches:
            db.session.commit()
            logger.info("Locked %d matches", len(matches))


def pull_results(app) -> None:
    """Pull finished match results from football-data.org."""
    from app.api.client import sync_results

    try:
        count = sync_results(app)
        if count:
            logger.info("Pulled results for %d matches", count)
    except Exception as exc:
        logger.error("Scheduled result pull failed: %s", exc)


def start_scheduler(app) -> None:
    global _scheduler

    # Under Werkzeug's reloader the parent process also imports the app.
    # Only the child process (WERKZEUG_RUN_MAIN=true) should run the scheduler.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        lock_expired_matches,
        trigger=IntervalTrigger(minutes=1),
        args=[app],
        id="lock_matches",
        replace_existing=True,
    )
    _scheduler.add_job(
        pull_results,
        trigger=IntervalTrigger(minutes=5),
        args=[app],
        id="pull_results",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started")
