from functools import wraps

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

from app.admin import admin_bp
from app.models import AppSettings, Match, Prediction, ResultSourceEnum, User, db
from app.scoring import recalculate_all_totals, score_match


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated


class ResultForm(FlaskForm):
    home_score = IntegerField("Home Score", validators=[DataRequired(), NumberRange(min=0, max=99)])
    away_score = IntegerField("Away Score", validators=[DataRequired(), NumberRange(min=0, max=99)])
    submit = SubmitField("Save Result")


class SettingsForm(FlaskForm):
    invite_code = StringField("Invite Code", validators=[DataRequired(), Length(max=100)])
    lock_minutes_before = IntegerField(
        "Lock Minutes Before",
        validators=[DataRequired(), NumberRange(min=0, max=1440)],
    )
    submit = SubmitField("Save Settings")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    unsettled = (
        Match.query.filter(Match.home_score.is_(None))
        .order_by(Match.match_datetime)
        .all()
    )
    return render_template("admin/dashboard.html", unsettled=unsettled)


@admin_bp.route("/matches/<int:match_id>/result", methods=["GET", "POST"])
@login_required
@admin_required
def set_result(match_id: int):
    match = Match.query.get_or_404(match_id)
    form = ResultForm(obj=match)

    if form.validate_on_submit():
        was_locked = match.is_locked
        match.home_score = form.home_score.data
        match.away_score = form.away_score.data
        match.is_locked = True
        match.result_source = (
            ResultSourceEnum.API_CORRECTED if match.result_source else ResultSourceEnum.MANUAL
        )
        score_match(match)
        db.session.commit()
        flash(f"Result saved: {match.home_score}–{match.away_score}", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/set_result.html", match=match, form=form)


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    app_settings = db.session.get(AppSettings, 1)
    form = SettingsForm(obj=app_settings)

    if form.validate_on_submit():
        app_settings.invite_code = form.invite_code.data
        app_settings.lock_minutes_before = form.lock_minutes_before.data
        db.session.commit()
        flash("Settings updated.", "success")
        return redirect(url_for("admin.settings"))

    return render_template("admin/settings.html", form=form)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot change your own admin status.", "warning")
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        status = "promoted to admin" if user.is_admin else "demoted"
        flash(f"{user.username} {status}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/recalculate", methods=["POST"])
@login_required
@admin_required
def recalculate():
    match_id = request.form.get("match_id", type=int)
    if match_id:
        match = Match.query.get_or_404(match_id)
        if match.has_result:
            count = score_match(match)
            db.session.commit()
            flash(f"Recalculated {count} predictions for match {match_id}.", "success")
        else:
            flash("Match has no result yet.", "warning")
    else:
        recalculate_all_totals()
        db.session.commit()
        flash("All totals recalculated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/api-sync", methods=["POST"])
@login_required
@admin_required
def api_sync():
    from flask import current_app

    from app.api.client import sync_results

    count = sync_results(current_app._get_current_object())
    flash(f"API sync complete. Updated {count} match(es).", "success")
    return redirect(url_for("admin.dashboard"))
