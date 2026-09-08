"""Typed application settings, sourced entirely from the environment (E1-S2).

Every environment-specific value the backend needs is declared here once; no
service reads `os.environ` and no module hardcodes a connection string, a secret
or the drift threshold. A missing required variable fails loudly at construction
with the variable's name in the message rather than yielding a `Settings` object
carrying `None` (E1-S2 AC2, deployment.md §5.3).
"""

from collections.abc import Sequence

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Variables with no safe default: the application cannot run without a real value.
REQUIRED_ENVIRONMENT_VARIABLES = ("DATABASE_URL", "JWT_SECRET")

DEFAULT_DRIFT_THRESHOLD_PERCENT = 5
DEFAULT_JWT_ACCESS_TOKEN_EXPIRY_MINUTES = 60
DEFAULT_SEED_CSV_PATH = "seed"

# The only environment is local dev (deployment.md §1.1): the Vite dev server at
# this origin is the sole browser client, and deployment.md §1.1 states the
# backend allows it "only" — no staging/production origin exists to add here.
DEFAULT_CORS_ALLOWED_ORIGINS = "http://localhost:5173"

# `RebalancingThreshold.threshold_bps`'s valid range (data-models.md §4.15's CHECK
# constraint, `threshold_bps BETWEEN 1 AND 10000`). Lives here, not in
# `domain/rebalancing/threshold_repository.py`, so no threshold-named literal is
# hardcoded outside config (E1-S2 AC4, test_no_drift_threshold_literal_outside_config).
MIN_THRESHOLD_BPS = 1
MAX_THRESHOLD_BPS = 10000


class MissingEnvironmentVariableError(RuntimeError):
    """Raised at start-up when a required environment variable is absent or empty."""

    def __init__(self, variable_names: Sequence[str]) -> None:
        self.variable_names = tuple(variable_names)
        super().__init__(
            "Missing required environment variable(s): "
            + ", ".join(self.variable_names)
            + ". Copy backend/.env.example to backend/.env and set a value for each."
        )


class Settings(BaseSettings):
    """Environment-driven configuration for the WealthWise backend.

    `default_drift_threshold_percent` seeds `RebalancingThreshold` version 1 only;
    the rebalancing service reads the active threshold row at runtime, never this
    value (system-design.md §6.1).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    jwt_access_token_expiry_minutes: int = DEFAULT_JWT_ACCESS_TOKEN_EXPIRY_MINUTES
    default_drift_threshold_percent: int = DEFAULT_DRIFT_THRESHOLD_PERCENT
    seed_csv_path: str = DEFAULT_SEED_CSV_PATH
    cors_allowed_origins: str = DEFAULT_CORS_ALLOWED_ORIGINS

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        """`cors_allowed_origins` split on commas for `CORSMiddleware(allow_origins=...)`.

        A single comma-separated env var (matching every other `Settings` field's
        shape) rather than a list-typed field, which `pydantic-settings` would
        otherwise expect as JSON in the environment (deployment.md §1.1 names one
        origin today; comma-splitting costs nothing and needs no future migration
        if that ever changes).
        """
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="before")
    @classmethod
    def _reject_missing_required_variables(cls, values: dict[str, object]) -> dict[str, object]:
        missing = [
            name for name in REQUIRED_ENVIRONMENT_VARIABLES if not values.get(name.lower())
        ]
        if missing:
            raise MissingEnvironmentVariableError(missing)
        return values
