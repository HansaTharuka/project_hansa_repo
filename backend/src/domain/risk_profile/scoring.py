"""Deterministic risk-band scoring (E4-S2) — pure integer arithmetic mapping a
completed questionnaire answer set to a risk band via the active `RiskBandRule`.

Every quantity here is a Python `int` — question points and band thresholds are
authored as integers in `questionnaire_json`/`scoring_rules_json`
(types/entities.py's `QuestionOption.points`, `BandRange.min_points/max_points`)
— so no floating-point comparison ever enters the scoring path (AC5). Calling
this function twice with an identical `answers` dict always returns the
identical risk band (AC1): there is no randomness, no wall-clock read, and no
mutable module-level state anywhere in this module.
"""

from __future__ import annotations

from src.types.entities import RiskBandRule
from src.types.errors import ValidationError


def score_answers(answers: dict[str, str], rule: RiskBandRule) -> str:
    """Map a complete `answers` dict (`question_id` -> selected option value)
    to the risk band whose `scoring_rules_json` range contains the total point
    count (AC1).

    Raises `ValidationError` (`INCOMPLETE_QUESTIONNAIRE`) if `answers` omits
    any question `rule.questionnaire_json` requires (AC2) — before a single
    point is totalled — and `ValidationError` (`INVALID_ANSWER`) if a supplied
    value is not one of that question's option values.
    """
    _validate_completeness(answers, rule)
    total_points = _total_points(answers, rule)
    return _band_for_points(total_points, rule)


def _validate_completeness(answers: dict[str, str], rule: RiskBandRule) -> None:
    required_ids = {question.question_id for question in rule.questionnaire_json.questions}
    missing = sorted(required_ids - answers.keys())
    if missing:
        raise ValidationError(
            f"Answer set is missing {len(missing)} required question(s): {missing}.",
            code="INCOMPLETE_QUESTIONNAIRE",
            details={"missing_question_ids": tuple(missing)},
        )


def _total_points(answers: dict[str, str], rule: RiskBandRule) -> int:
    points_by_question = {
        question.question_id: {option.value: option.points for option in question.options}
        for question in rule.questionnaire_json.questions
    }
    total = 0
    for question_id, answer_value in answers.items():
        options = points_by_question.get(question_id)
        if options is None or answer_value not in options:
            raise ValidationError(
                f"{answer_value!r} is not a valid option for question {question_id!r}.",
                code="INVALID_ANSWER",
                details={"question_id": question_id, "answer_value": answer_value},
            )
        total += options[answer_value]
    return total


def _band_for_points(total_points: int, rule: RiskBandRule) -> str:
    for band_range in rule.scoring_rules_json.bands:
        if band_range.min_points <= total_points <= band_range.max_points:
            return band_range.risk_band.value
    raise ValidationError(
        f"No configured risk band covers a point total of {total_points}.",
        code="SCORE_OUT_OF_RANGE",
        details={"total_points": total_points},
    )
