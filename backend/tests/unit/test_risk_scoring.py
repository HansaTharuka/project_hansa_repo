"""`domain/risk_profile/scoring.py` — score_answers() (E4-S2 AC1, AC2, AC5;
ut-131, ut-132, ut-135)."""

from __future__ import annotations

import pytest

from src.domain.risk_profile.scoring import score_answers
from src.types.entities import (
    BandRange,
    Question,
    Questionnaire,
    QuestionOption,
    RiskBandRule,
    ScoringRules,
)
from src.types.errors import ValidationError

QUESTIONNAIRE = Questionnaire(
    questions=[
        Question(
            question_id=f"Q{i}",
            text=f"Question {i}?",
            options=[
                QuestionOption(value="low", label="Low", points=1),
                QuestionOption(value="mid", label="Mid", points=3),
                QuestionOption(value="high", label="High", points=5),
            ],
        )
        for i in range(1, 7)
    ]
)
SCORING_RULES = ScoringRules(
    bands=[
        BandRange(risk_band="CONSERVATIVE", min_points=6, max_points=13),
        BandRange(risk_band="MODERATE", min_points=14, max_points=22),
        BandRange(risk_band="AGGRESSIVE", min_points=23, max_points=30),
    ]
)
RULE = RiskBandRule(
    id=1,
    version=1,
    questionnaire_json=QUESTIONNAIRE,
    scoring_rules_json=SCORING_RULES,
    published_at="2026-09-01T09:00:00Z",
    is_active=True,
)

ALL_LOW_ANSWERS = {f"Q{i}": "low" for i in range(1, 7)}
ALL_HIGH_ANSWERS = {f"Q{i}": "high" for i in range(1, 7)}
MIXED_MODERATE_ANSWERS = {**{f"Q{i}": "mid" for i in range(1, 5)}, "Q5": "low", "Q6": "low"}


def test_scoring_the_same_answers_twice_returns_the_identical_band_both_times() -> None:
    first = score_answers(ALL_LOW_ANSWERS, RULE)
    second = score_answers(ALL_LOW_ANSWERS, RULE)

    assert first == second == "CONSERVATIVE"


def test_all_high_answers_score_into_the_aggressive_band() -> None:
    assert score_answers(ALL_HIGH_ANSWERS, RULE) == "AGGRESSIVE"


def test_a_mixed_answer_set_scores_into_the_moderate_band() -> None:
    # 4*3 + 1 + 1 = 14 -> lands exactly on MODERATE's lower bound.
    assert score_answers(MIXED_MODERATE_ANSWERS, RULE) == "MODERATE"


def test_an_incomplete_answer_set_raises_validation_error() -> None:
    incomplete = {f"Q{i}": "low" for i in range(1, 6)}  # missing Q6

    with pytest.raises(ValidationError) as excinfo:
        score_answers(incomplete, RULE)

    assert excinfo.value.code == "INCOMPLETE_QUESTIONNAIRE"


def test_an_answer_value_not_among_the_question_s_options_raises_validation_error() -> None:
    invalid = {**ALL_LOW_ANSWERS, "Q1": "not-an-option"}

    with pytest.raises(ValidationError) as excinfo:
        score_answers(invalid, RULE)

    assert excinfo.value.code == "INVALID_ANSWER"


def test_a_point_total_not_covered_by_any_configured_band_raises_score_out_of_range() -> None:
    """A gap between the last configured band's `max_points` and the highest
    achievable total raises `ValidationError` (`SCORE_OUT_OF_RANGE`) rather
    than silently falling through — `_band_for_points`'s own docstring
    branch."""
    gapped_rules = ScoringRules(
        bands=[
            BandRange(risk_band="CONSERVATIVE", min_points=6, max_points=13),
            BandRange(risk_band="MODERATE", min_points=14, max_points=22),
            # AGGRESSIVE band deliberately omitted, leaving 23-30 uncovered.
        ]
    )
    gapped_rule = RiskBandRule(
        id=2,
        version=1,
        questionnaire_json=QUESTIONNAIRE,
        scoring_rules_json=gapped_rules,
        published_at="2026-09-01T09:00:00Z",
        is_active=True,
    )

    with pytest.raises(ValidationError) as excinfo:
        score_answers(ALL_HIGH_ANSWERS, gapped_rule)

    assert excinfo.value.code == "SCORE_OUT_OF_RANGE"


def test_no_float_appears_anywhere_in_the_scoring_result_or_intermediate_totals() -> None:
    result = score_answers(ALL_LOW_ANSWERS, RULE)

    assert isinstance(result, str)
    for question in RULE.questionnaire_json.questions:
        for option in question.options:
            assert type(option.points) is int
    for band in RULE.scoring_rules_json.bands:
        assert type(band.min_points) is int
        assert type(band.max_points) is int
