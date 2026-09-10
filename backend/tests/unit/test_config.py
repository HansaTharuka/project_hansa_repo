"""E1-S2 AC1–AC5 — typed settings, loud startup failures and documented env vars.

Covers ut-013 – ut-025 and ut-030. Every construction passes `_env_file=None` so a
developer's local `backend/.env` can never leak into a test result.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, get_args

import pytest

from src.core.config import MissingEnvironmentVariableError, Settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
CONFIG_MODULE = BACKEND_ROOT / "src" / "core" / "config.py"
BACKEND_ENV_EXAMPLE = BACKEND_ROOT / ".env.example"
FRONTEND_ENV_EXAMPLE = REPO_ROOT / "frontend" / ".env.example"
GITIGNORE = REPO_ROOT / ".gitignore"

# deployment.md §5.1, §1.1 (CORS_ALLOWED_ORIGINS).
DOCUMENTED_BACKEND_VARS = {
    "DATABASE_URL",
    "JWT_SECRET",
    "JWT_ACCESS_TOKEN_EXPIRY_MINUTES",
    "DEFAULT_DRIFT_THRESHOLD_PERCENT",
    "SEED_CSV_PATH",
    "LOG_LEVEL",
    "CORS_ALLOWED_ORIGINS",
}
REQUIRED_SETTINGS = {
    "database_url",
    "jwt_secret",
    "jwt_access_token_expiry_minutes",
    "default_drift_threshold_percent",
    "seed_csv_path",
}
SECRET_BEARING_SETTINGS = ("database_url", "jwt_secret")

# folder-structure.md §5.
GITIGNORE_REQUIRED_ENTRIES = [
    "backend/.env",
    "backend/*.db",
    "backend/.venv/",
    "backend/.pytest_cache/",
    "backend/htmlcov/",
    "backend/.coverage",
    "frontend/.env",
    "frontend/node_modules/",
    "frontend/dist/",
    "frontend/coverage/",
]

VALID_ENV = {
    "DATABASE_URL": "sqlite:///./wealthwise.db",
    "JWT_SECRET": "local-development-only-not-a-real-secret",
    "SEED_CSV_PATH": "seed",
}


def parse_env_file(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def settings_env_names() -> set[str]:
    prefix = str(Settings.model_config.get("env_prefix") or "")
    return {f"{prefix}{name}".upper() for name in Settings.model_fields}


def build_settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every WealthWise variable so defaults and failures are observable."""
    for name in DOCUMENTED_BACKEND_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class TestTypedSettings:
    """ut-013, ut-030 — concrete annotations, integers where the spec says integer."""

    @pytest.mark.parametrize("field", sorted(REQUIRED_SETTINGS))
    def test_setting_is_declared(self, field: str) -> None:
        assert field in Settings.model_fields

    @pytest.mark.parametrize("field", sorted(REQUIRED_SETTINGS))
    def test_setting_has_a_concrete_non_nullable_annotation(self, field: str) -> None:
        annotation = Settings.model_fields[field].annotation
        assert annotation is not Any and annotation is not None
        assert type(None) not in get_args(annotation), f"{field} must not be Optional"

    @pytest.mark.parametrize(
        ("field", "expected"),
        [
            ("database_url", str),
            ("jwt_secret", str),
            ("jwt_access_token_expiry_minutes", int),
            ("default_drift_threshold_percent", int),
            ("seed_csv_path", str),
        ],
    )
    def test_setting_annotation_matches_the_spec(self, field: str, expected: type) -> None:
        assert Settings.model_fields[field].annotation is expected

    def test_config_module_contains_no_float(self) -> None:
        tree = ast.parse(CONFIG_MODULE.read_text(encoding="utf-8"))
        offences = [
            node.lineno
            for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and node.id == "float")
            or (isinstance(node, ast.Constant) and type(node.value) is float)
        ]
        assert offences == []


class TestDefaults:
    """ut-014, ut-015 — the documented defaults from deployment.md §5.1."""

    def test_drift_threshold_defaults_to_five_percent(self, clean_env: pytest.MonkeyPatch) -> None:
        for name, value in VALID_ENV.items():
            clean_env.setenv(name, value)
        assert build_settings().default_drift_threshold_percent == 5

    def test_access_token_expiry_defaults_to_sixty_minutes(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for name, value in VALID_ENV.items():
            clean_env.setenv(name, value)
        assert build_settings().jwt_access_token_expiry_minutes == 60

    def test_defaults_are_whole_integers_not_strings_or_floats(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        for name, value in VALID_ENV.items():
            clean_env.setenv(name, value)
        settings = build_settings()
        assert type(settings.default_drift_threshold_percent) is int
        assert type(settings.jwt_access_token_expiry_minutes) is int


class TestEnvironmentLoading:
    """ut-016 — every value comes from the environment, coerced to its declared type."""

    def test_all_settings_reflect_the_environment(self, clean_env: pytest.MonkeyPatch) -> None:
        # Arrange
        clean_env.setenv("DATABASE_URL", "sqlite:///./wealthwise-test.db")
        clean_env.setenv("JWT_SECRET", "local-development-only-not-a-real-secret")
        clean_env.setenv("JWT_ACCESS_TOKEN_EXPIRY_MINUTES", "15")
        clean_env.setenv("DEFAULT_DRIFT_THRESHOLD_PERCENT", "7")
        clean_env.setenv("SEED_CSV_PATH", "seed/asset_classes.csv")
        # Act
        settings = build_settings()
        # Assert
        assert settings.database_url == "sqlite:///./wealthwise-test.db"
        assert settings.jwt_secret == "local-development-only-not-a-real-secret"
        assert settings.seed_csv_path == "seed/asset_classes.csv"

    def test_numeric_variables_are_parsed_as_int(self, clean_env: pytest.MonkeyPatch) -> None:
        for name, value in VALID_ENV.items():
            clean_env.setenv(name, value)
        clean_env.setenv("JWT_ACCESS_TOKEN_EXPIRY_MINUTES", "15")
        clean_env.setenv("DEFAULT_DRIFT_THRESHOLD_PERCENT", "7")
        settings = build_settings()
        assert settings.jwt_access_token_expiry_minutes == 15
        assert settings.default_drift_threshold_percent == 7
        assert type(settings.default_drift_threshold_percent) is int


class TestMissingRequiredVariables:
    """ut-017 – ut-019 — a missing required variable is a loud startup failure."""

    def test_missing_database_url_raises(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("JWT_SECRET", "local-development-only-not-a-real-secret")
        with pytest.raises(MissingEnvironmentVariableError):
            build_settings()

    def test_missing_jwt_secret_raises(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("DATABASE_URL", "sqlite:///./wealthwise.db")
        with pytest.raises(MissingEnvironmentVariableError):
            build_settings()

    def test_empty_jwt_secret_is_not_accepted_as_a_fallback(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        clean_env.setenv("DATABASE_URL", "sqlite:///./wealthwise.db")
        clean_env.setenv("JWT_SECRET", "")
        with pytest.raises(MissingEnvironmentVariableError):
            build_settings()

    def test_error_message_names_the_missing_variable(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("DATABASE_URL", "sqlite:///./wealthwise.db")
        with pytest.raises(MissingEnvironmentVariableError) as raised:
            build_settings()
        assert "JWT_SECRET" in str(raised.value)

    def test_error_message_names_every_missing_variable(
        self, clean_env: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(MissingEnvironmentVariableError) as raised:
            build_settings()
        message = str(raised.value)
        assert "DATABASE_URL" in message and "JWT_SECRET" in message


class TestNoHardcodedSecretsOrThresholds:
    """ut-020, ut-021 — secrets and the drift threshold live only in config."""

    @pytest.mark.parametrize("field", SECRET_BEARING_SETTINGS)
    def test_secret_bearing_setting_has_no_hardcoded_default(self, field: str) -> None:
        assert Settings.model_fields[field].is_required(), f"{field} must have no default"

    def test_config_module_assigns_no_secret_literal(self) -> None:
        tree = ast.parse(CONFIG_MODULE.read_text(encoding="utf-8"))
        secretish = re.compile(r"secret|password|token|credential|api_key", re.IGNORECASE)
        offences = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign | ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and any(secretish.search(name) for name in assigned_names(node))
        ]
        assert offences == []

    def test_no_drift_threshold_literal_outside_config(self) -> None:
        assert threshold_literal_offences() == []

    def test_the_threshold_scan_recognises_an_offending_module(self, tmp_path: Path) -> None:
        offending = tmp_path / "service.py"
        offending.write_text("drift_threshold = 500\n", encoding="utf-8")
        assert threshold_literal_offences((offending,)) == ["service.py:1 drift_threshold"]


class TestEnvExampleFiles:
    """ut-022 – ut-024 — the documented environment surface."""

    def test_backend_env_example_documents_exactly_the_seven_variables(self) -> None:
        assert set(parse_env_file(BACKEND_ENV_EXAMPLE)) == DOCUMENTED_BACKEND_VARS

    def test_every_variable_settings_reads_is_documented(self) -> None:
        assert settings_env_names() <= set(parse_env_file(BACKEND_ENV_EXAMPLE))

    def test_every_backend_placeholder_is_non_empty(self) -> None:
        entries = parse_env_file(BACKEND_ENV_EXAMPLE)
        assert all(value for value in entries.values()), entries

    def test_jwt_secret_placeholder_is_not_a_real_credential(self) -> None:
        placeholder = parse_env_file(BACKEND_ENV_EXAMPLE)["JWT_SECRET"]
        assert not re.fullmatch(r"[0-9a-fA-F]{64}", placeholder)
        assert "change" in placeholder.lower() or "placeholder" in placeholder.lower()

    def test_frontend_env_example_documents_the_api_base_url(self) -> None:
        assert parse_env_file(FRONTEND_ENV_EXAMPLE) == {
            "VITE_API_BASE_URL": "http://localhost:8000"
        }


class TestGitignore:
    """ut-025 — no real secret, database file or build artefact can be staged."""

    @pytest.mark.parametrize("entry", GITIGNORE_REQUIRED_ENTRIES)
    def test_gitignore_contains_the_required_entry(self, entry: str) -> None:
        lines = {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}
        assert entry in lines

    def test_env_example_files_are_not_ignored(self) -> None:
        lines = {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}
        assert not lines & {".env.example", "backend/.env.example", "frontend/.env.example"}

    @pytest.mark.parametrize("env_path", ["backend/.env", "frontend/.env"])
    def test_no_real_env_file_exists_on_disk(self, env_path: str) -> None:
        assert not (REPO_ROOT / env_path).exists()


def assigned_names(node: ast.AnnAssign | ast.Assign) -> list[str]:
    targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
    return [target.id for target in targets if isinstance(target, ast.Name)]


def threshold_literal_offences(modules: tuple[Path, ...] | None = None) -> list[str]:
    """Numeric literals bound to a threshold- or drift-named symbol outside config.py."""
    scanned = modules or tuple(
        path for path in sorted((BACKEND_ROOT / "src").rglob("*.py")) if path != CONFIG_MODULE
    )
    hint = re.compile(r"threshold|drift", re.IGNORECASE)
    offences: list[str] = []
    for module in scanned:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign | ast.Assign):
                continue
            value = node.value
            if not isinstance(value, ast.Constant) or isinstance(value.value, bool | str):
                continue
            if not isinstance(value.value, int | float):
                continue
            offences += [
                f"{module.name}:{node.lineno} {name}"
                for name in assigned_names(node)
                if hint.search(name)
            ]
    return offences
