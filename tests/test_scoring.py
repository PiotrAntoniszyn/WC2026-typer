"""
Pure unit tests for scoring logic — no database required.
Uses simple namespace objects to avoid model imports.
"""
from types import SimpleNamespace

import pytest

from app.scoring import (
    POINTS_CHAMPION,
    POINTS_EXACT_GROUP,
    POINTS_EXACT_KO,
    POINTS_OUTCOME_GROUP,
    POINTS_OUTCOME_KO,
    calculate_champion_points,
    calculate_points,
)
from app.models import PhaseEnum


def _pred(home: int, away: int, champion_id: int | None = None):
    return SimpleNamespace(home_score=home, away_score=away, champion_team_id=champion_id)


def _match(home: int, away: int, phase: PhaseEnum = PhaseEnum.GROUP):
    return SimpleNamespace(home_score=home, away_score=away, phase=phase)


# --- Group stage ---

def test_exact_score_group():
    assert calculate_points(_pred(2, 1), _match(2, 1)) == POINTS_EXACT_GROUP


def test_correct_outcome_home_win_group():
    assert calculate_points(_pred(3, 0), _match(1, 0)) == POINTS_OUTCOME_GROUP


def test_correct_outcome_draw_group():
    assert calculate_points(_pred(0, 0), _match(1, 1)) == POINTS_OUTCOME_GROUP


def test_correct_outcome_away_win_group():
    assert calculate_points(_pred(0, 2), _match(0, 1)) == POINTS_OUTCOME_GROUP


def test_wrong_prediction_group():
    assert calculate_points(_pred(2, 0), _match(0, 1)) == 0


# --- Knockout phases ---

@pytest.mark.parametrize("phase", [
    PhaseEnum.R32, PhaseEnum.R16, PhaseEnum.QF,
    PhaseEnum.SF, PhaseEnum.THIRD, PhaseEnum.FINAL,
])
def test_exact_score_knockout(phase):
    assert calculate_points(_pred(1, 0), _match(1, 0, phase)) == POINTS_EXACT_KO


@pytest.mark.parametrize("phase", [PhaseEnum.R16, PhaseEnum.QF, PhaseEnum.FINAL])
def test_correct_outcome_knockout(phase):
    assert calculate_points(_pred(2, 0), _match(1, 0, phase)) == POINTS_OUTCOME_KO


def test_wrong_prediction_knockout():
    assert calculate_points(_pred(0, 2), _match(1, 0, PhaseEnum.FINAL)) == 0


# --- Champion bonus ---

def test_champion_correct():
    pred = _pred(0, 0, champion_id=5)
    assert calculate_champion_points(pred, champion_team_id=5) == POINTS_CHAMPION


def test_champion_wrong():
    pred = _pred(0, 0, champion_id=3)
    assert calculate_champion_points(pred, champion_team_id=7) == 0


def test_champion_no_pick():
    pred = _pred(0, 0, champion_id=None)
    assert calculate_champion_points(pred, champion_team_id=5) == 0
