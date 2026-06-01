from collections import defaultdict
from datetime import datetime, timezone

from flask import redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from app.main import main_bp
from app.models import Match, PhaseEnum, Prediction, Team, User
from app.scoring import (
    POINTS_EXACT_GROUP,
    POINTS_EXACT_KO,
    POINTS_OUTCOME_GROUP,
    POINTS_OUTCOME_KO,
)


@main_bp.route("/")
def index():
    now = datetime.now(timezone.utc)
    upcoming = (
        Match.query
        .filter(Match.match_datetime >= now)
        .filter(~Match.home_team.has(Team.country_code == "TBD"))
        .filter(~Match.away_team.has(Team.country_code == "TBD"))
        .order_by(Match.match_datetime)
        .limit(3)
        .all()
    )
    top_users = User.query.order_by(User.total_points.desc()).limit(5).all()
    user_predictions = {}
    if current_user.is_authenticated:
        preds = (
            Prediction.query
            .filter_by(user_id=current_user.id)
            .filter(Prediction.match_id.isnot(None))
            .all()
        )
        user_predictions = {p.match_id: p for p in preds}
    return render_template("main/index.html", upcoming=upcoming, top_users=top_users, user_predictions=user_predictions)


@main_bp.route("/matches")
def matches():
    all_matches = (
        Match.query
        .filter(~Match.home_team.has(Team.country_code == "TBD"))
        .filter(~Match.away_team.has(Team.country_code == "TBD"))
        .order_by(Match.match_datetime)
        .all()
    )

    # Group by phase, then group_letter within group stage
    by_phase: dict[PhaseEnum, dict[str | None, list[Match]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for m in all_matches:
        by_phase[m.phase][m.group_letter].append(m)

    user_predictions = {}
    if current_user.is_authenticated:
        preds = (
            Prediction.query
            .filter_by(user_id=current_user.id)
            .filter(Prediction.match_id.isnot(None))
            .all()
        )
        user_predictions = {p.match_id: p for p in preds}

    sort_mode = request.args.get("sort", "phase")
    phase_order = list(PhaseEnum)
    return render_template(
        "main/matches.html",
        by_phase=by_phase,
        phase_order=phase_order,
        user_predictions=user_predictions,
        all_matches=all_matches,
        sort_mode=sort_mode,
    )


@main_bp.route("/matches/<int:match_id>")
@login_required
def match_detail(match_id: int):
    match = Match.query.get_or_404(match_id)

    user_prediction = None
    all_predictions = []

    if current_user.is_authenticated:
        user_prediction = Prediction.query.filter_by(
            user_id=current_user.id, match_id=match_id
        ).first()

    if match.is_locked:
        all_predictions = (
            Prediction.query.filter_by(match_id=match_id)
            .join(User)
            .order_by(Prediction.points_awarded.desc().nullslast(), User.username)
            .all()
        )

    return render_template(
        "main/match_detail.html",
        match=match,
        user_prediction=user_prediction,
        all_predictions=all_predictions,
    )


@main_bp.route("/leaderboard")
def leaderboard():
    users = User.query.order_by(User.total_points.desc()).all()

    scored_preds = (
        Prediction.query
        .join(Match, Prediction.match_id == Match.id)
        .filter(Prediction.points_awarded.isnot(None))
        .with_entities(
            Prediction.user_id,
            Prediction.points_awarded,
            Match.phase,
        )
        .all()
    )

    stats = defaultdict(lambda: {
        "exact_group": 0, "outcome_group": 0,
        "exact_ko": 0, "outcome_ko": 0,
    })
    for user_id, points, phase in scored_preds:
        s = stats[user_id]
        if phase.is_knockout:
            if points == POINTS_EXACT_KO:
                s["exact_ko"] += 1
            elif points == POINTS_OUTCOME_KO:
                s["outcome_ko"] += 1
        else:
            if points == POINTS_EXACT_GROUP:
                s["exact_group"] += 1
            elif points == POINTS_OUTCOME_GROUP:
                s["outcome_group"] += 1

    return render_template("main/leaderboard.html", users=users, stats=stats)


@main_bp.route("/rules")
def rules():
    return render_template("main/rules.html")


@main_bp.route("/set-lang/<lang>")
def set_lang(lang: str):
    if lang in ("en", "pl"):
        session["lang"] = lang
    referrer = request.referrer
    if referrer:
        from urllib.parse import urlparse
        ref = urlparse(referrer)
        if ref.scheme in ("http", "https") and ref.netloc == request.host:
            return redirect(referrer)
    return redirect(url_for("main.index"))


@main_bp.route("/profile")
@login_required
def profile():
    predictions = (
        Prediction.query.filter_by(user_id=current_user.id)
        .filter(Prediction.match_id.isnot(None))
        .join(Match)
        .order_by(Match.match_datetime.desc())
        .all()
    )
    champion_pred = Prediction.query.filter_by(
        user_id=current_user.id, match_id=None
    ).first()
    return render_template(
        "main/profile.html",
        predictions=predictions,
        champion_pred=champion_pred,
    )
