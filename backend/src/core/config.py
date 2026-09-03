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

    @model_validator(mode="before")
    @classmethod
    def _reject_missing_required_variables(cls, values: dict[str, object]) -> dict[str, object]:
        missing = [
            name for name in REQUIRED_ENVIRONMENT_VARIABLES if not values.get(name.lower())
        ]
        if missing:
            raise MissingEnvironmentVariableError(missing)
        return values
