"""`core/logging.py` PII/financial-value redaction (E1-S4 AC3; ut-048)."""

from __future__ import annotations

import json
import logging

from src.core.logging import REDACTED_MARKER, JsonFormatter, configure_logging, redact


def test_redact_masks_password_in_an_inbound_request_shaped_payload() -> None:
    payload = {"email": "customer@wealthwise.test", "password": "hunter2-plaintext"}

    result = redact(payload)

    assert result["password"] == REDACTED_MARKER
    assert result["email"] == "customer@wealthwise.test"
    assert "hunter2-plaintext" not in json.dumps(result)


def test_redact_masks_password_hash() -> None:
    result = redact({"password_hash": "$2b$12$somehash"})

    assert result["password_hash"] == REDACTED_MARKER


def test_redact_masks_raw_financial_values_in_an_outbound_response_shaped_payload() -> None:
    payload = {"customer_id": 3, "current_value": 1234567, "target_amount": 9999999}

    result = redact(payload)

    assert result["current_value"] == REDACTED_MARKER
    assert result["target_amount"] == REDACTED_MARKER
    assert result["customer_id"] == 3


def test_redact_leaves_non_sensitive_keys_untouched() -> None:
    payload = {"method": "GET", "path": "/health", "status_code": 200}

    result = redact(payload)

    assert result == payload


def test_json_formatter_never_emits_a_raw_password_or_financial_value_from_extra() -> None:
    record = logging.LogRecord(
        name="wealthwise.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.password = "hunter2-plaintext"  # type: ignore[attr-defined]
    record.current_value = 555000  # type: ignore[attr-defined]
    record.request_id = "abc-123"  # type: ignore[attr-defined]

    line = JsonFormatter().format(record)
    parsed = json.loads(line)

    assert parsed["password"] == REDACTED_MARKER
    assert parsed["current_value"] == REDACTED_MARKER
    assert parsed["request_id"] == "abc-123"
    assert "hunter2-plaintext" not in line


def test_configure_logging_re_enables_a_logger_disabled_by_logging_config_fileconfig() -> None:
    """`alembic/env.py` calls `logging.config.fileConfig()` on every migration run;
    that function's default `disable_existing_loggers=True` sets `.disabled = True`
    on any pre-existing logger not named in its config — including this
    application's own loggers, created at import time, before a migration ever
    runs. `configure_logging` must undo that or every app log line is silently
    dropped (E1-S4 AC2's request-log line would never reach any handler)."""
    victim = logging.getLogger("wealthwise.request")
    victim.disabled = True

    configure_logging()

    assert victim.disabled is False
    assert victim.isEnabledFor(logging.INFO)
