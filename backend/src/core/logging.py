"""Structured JSON logging (E1-S4 AC2, AC3) and the shared PII/financial redaction
helper every request/response-adjacent log call routes through (NFR-03).

`JsonFormatter` redacts `SENSITIVE_KEYS` at the sink — every `extra={...}` field
attached to a log record — so a call site that forgets to pre-redact a payload
still cannot leak a raw credential or financial-position value into a log line.
`redact()` is also exported directly for call sites (e.g. a future request-body
logger) that want to sanitize a payload before deciding whether to log it at all.
"""

from __future__ import annotations

import json
import logging
import sys

REDACTED_MARKER = "[REDACTED]"

# Keys whose value is never emitted verbatim in a log line, anywhere in the
# application (NFR-03): credential fields, plus every raw financial-position value
# a request/response body carries in later stories.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "current_value",
        "target_amount",
        "nav_value",
        "amount",
        "market_value",
    }
)

# A LogRecord's own baseline attributes — anything beyond this set on a record came
# from a caller's `extra={...}` and is a candidate for redaction.
_RESERVED_RECORD_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)))


def redact(payload: dict[str, object]) -> dict[str, object]:
    """Return a shallow copy of `payload` with every `SENSITIVE_KEYS` value masked."""
    return {
        key: REDACTED_MARKER if key in SENSITIVE_KEYS else value for key, value in payload.items()
    }


class JsonFormatter(logging.Formatter):
    """Renders one JSON object per log line; `extra={...}` fields are merged in,
    redacted, after the fixed `timestamp`/`level`/`logger`/`message` fields."""

    def format(self, record: logging.LogRecord) -> str:
        extra = {
            key: value
            for key, value in vars(record).items()
            if key not in _RESERVED_RECORD_ATTRS
        }
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **redact(extra),
        }
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotently attach a stdout JSON handler to the root logger.

    Adds, never replaces: other handlers already on the root logger — a test
    runner's own capture handler, or the handler `alembic/env.py`'s `fileConfig()`
    installs on every migration run — are left untouched. Calling this more than
    once (every app-startup lifespan run) never attaches a second JSON handler.

    Also re-enables every logger `logging.config.fileConfig()` may have disabled:
    that function's default `disable_existing_loggers=True` sets `.disabled = True`
    on any logger created before it runs and not named in its config section —
    which silently swallows every `wealthwise.*` logger the moment
    `alembic/env.py`'s own `fileConfig()` call runs a migration, since this
    application's loggers are created at import time, before that call. This is
    the reason `configure_logging` must run from the ASGI lifespan's startup
    phase (see `app/main.py`), not at import time: it is the one point guaranteed
    to run *after* any migration this process has already performed.
    """
    root = logging.getLogger()
    root.setLevel(level)
    root.disabled = False
    for logger in root.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.disabled = False
    already_attached = any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
    if not already_attached:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger under `name`. Call `configure_logging` once at app start."""
    return logging.getLogger(name)
