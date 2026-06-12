from datetime import UTC, datetime, timedelta

from flask import flash, redirect, render_template, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import AppSettings, Match, Prediction, Team, db
from app.predict import predict_bp
from app.predict.forms import ChampionForm, PredictionForm


@predict_bp.route("/matches/<int:match_id>/predict", methods=["POST"])
@login_required
def save_prediction(match_id: int):
    match = Match.query.get_or_404(match_id)

    if match.is_locked:
        flash(_("Predictions are locked for this match."), "warning")
        return redirect(url_for("main.match_detail", match_id=match_id))

    # Enforce lock window even if is_locked flag hasn't been set by scheduler yet
    settings = db.session.get(AppSettings, 1)
    lock_minutes = settings.lock_minutes_before if settings else 60
    lock_cutoff = match.match_datetime.replace(tzinfo=UTC) - timedelta(minutes=lock_minutes)
    if datetime.now(UTC) >= lock_cutoff:
        match.is_locked = True
        db.session.commit()
        flash(_("The prediction window for this match has closed."), "warning")
        return redirect(url_for("main.match_detail", match_id=match_id))

    form = PredictionForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for error in field_errors:
                flash(error, "danger")
        return redirect(url_for("main.match_detail", match_id=match_id))

    existing = Prediction.query.filter_by(
        user_id=current_user.id, match_id=match_id
    ).first()

    if existing:
        existing.home_score = form.home_score.data
        existing.away_score = form.away_score.data
    else:
        pred = Prediction(
            user_id=current_user.id,
            match_id=match_id,
            home_score=form.home_score.data,
            away_score=form.away_score.data,
        )
        db.session.add(pred)

    db.session.commit()
    flash(_("Prediction saved."), "success")
    return redirect(url_for("main.matches"))


CHAMPION_DEADLINE = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


@predict_bp.route("/champion", methods=["GET", "POST"])
def champion():
    window_open = datetime.now(UTC) < CHAMPION_DEADLINE

    teams = Team.query.filter(Team.country_code != "TBD").order_by(Team.name).all()
    form = ChampionForm()
    form.champion_team_id.choices = [(t.id, t.name) for t in teams]

    existing = None
    if current_user.is_authenticated:
        existing = Prediction.query.filter_by(
            user_id=current_user.id, match_id=None
        ).first()

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash(_("Log in to make a champion pick."), "warning")
            return redirect(url_for("auth.login"))

        if not window_open:
            flash(_("The champion prediction window is closed."), "warning")
            return redirect(url_for("predict.champion"))

        if existing:
            existing.champion_team_id = form.champion_team_id.data
        else:
            pred = Prediction(
                user_id=current_user.id,
                match_id=None,
                home_score=0,
                away_score=0,
                champion_team_id=form.champion_team_id.data,
            )
            db.session.add(pred)

        db.session.commit()
        flash(_("Champion pick saved."), "success")
        return redirect(url_for("predict.champion"))

    # Pre-fill form with existing pick
    if existing and existing.champion_team_id:
        form.champion_team_id.data = existing.champion_team_id

    return render_template(
        "predict/champion.html",
        form=form,
        window_open=window_open,
        existing=existing,
        teams=teams,
        deadline=CHAMPION_DEADLINE,
    )
