"""
Pure scoring functions — no Flask context required.
Callers are responsible for db.session.commit() after mutations.
"""
import logging

logger = logging.getLogger(__name__)

POINTS_EXACT_GROUP = 3
POINTS_OUTCOME_GROUP = 1
POINTS_EXACT_KO = 5
POINTS_OUTCOME_KO = 2
POINTS_CHAMPION = 20


def _outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def calculate_points(prediction, match) -> int:
    """
    Returns points for a single match prediction.
    Does NOT mutate — caller writes prediction.points_awarded.
    """
    assert match.home_score is not None and match.away_score is not None, (
        f"Match {match.id} has no result"
    )

    is_ko = match.phase.is_knockout
    exact = (
        prediction.home_score == match.home_score
        and prediction.away_score == match.away_score
    )
    correct_outcome = _outcome(prediction.home_score, prediction.away_score) == _outcome(
        match.home_score, match.away_score
    )

    if exact:
        return POINTS_EXACT_KO if is_ko else POINTS_EXACT_GROUP
    if correct_outcome:
        return POINTS_OUTCOME_KO if is_ko else POINTS_OUTCOME_GROUP
    return 0


def calculate_champion_points(prediction, champion_team_id: int) -> int:
    """Returns 20 if the champion pick is correct, else 0."""
    if prediction.champion_team_id == champion_team_id:
        return POINTS_CHAMPION
    return 0


def score_match(match) -> int:
    """
    Scores all Predictions for a settled match using delta updates.
    Returns count of predictions scored.
    Caller must commit.
    """
    if not match.has_result:
        raise ValueError(f"Match {match.id} has no result yet")

    count = 0
    for prediction in match.predictions:
        old_points = prediction.points_awarded or 0
        new_points = calculate_points(prediction, match)
        prediction.points_awarded = new_points
        # Delta update preserves correctness when a result is later corrected
        prediction.user.total_points += new_points - old_points
        count += 1

    logger.info("Scored %d predictions for match %d", count, match.id)
    return count


def score_champion(champion_team_id: int) -> int:
    """
    Awards champion bonus to all users whose champion pick is correct.
    Returns count of users awarded points.
    Caller must commit.
    """
    from app.models import Prediction

    count = 0
    champion_preds = Prediction.query.filter(
        Prediction.match_id.is_(None),
        Prediction.champion_team_id.isnot(None),
    ).all()

    for pred in champion_preds:
        old_points = pred.points_awarded or 0
        new_points = calculate_champion_points(pred, champion_team_id)
        pred.points_awarded = new_points
        pred.user.total_points += new_points - old_points
        if new_points > 0:
            count += 1

    return count


def recalculate_all_totals() -> None:
    """
    Resets all User.total_points to 0 then re-sums from Prediction records.
    Use after bulk result corrections. Caller must commit.
    """
    from app.models import Prediction, User

    for user in User.query.all():
        user.total_points = 0

    for pred in Prediction.query.filter(Prediction.points_awarded.isnot(None)).all():
        pred.user.total_points += pred.points_awarded
