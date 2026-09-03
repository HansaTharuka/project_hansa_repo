"""NFR-01 / E1-S1 AC2 — no float anywhere in the fixed-point source trees.

Scope grows with the codebase (component-map.md note 5): group A delivers
`src/types/` and `src/core/`, so both are scanned here. E1-S3 and the domain
stories extend SCANNED_PACKAGES to `src/db/` and `src/domain/`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCANNED_PACKAGES = ("src/types", "src/core")


def scanned_modules() -> list[Path]:
    modules = [
        path
        for package in SCANNED_PACKAGES
        for path in sorted((BACKEND_ROOT / package).rglob("*.py"))
    ]
    assert modules, "no modules found to scan — check SCANNED_PACKAGES"
    return modules


def float_offences(module: Path) -> list[str]:
    """Return one description per float annotation, float() call or float literal."""
    tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
    offences: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "float":
            offences.append(f"{module.name}:{node.lineno} references the name 'float'")
        elif isinstance(node, ast.Attribute) and node.attr == "float":
            offences.append(f"{module.name}:{node.lineno} references an attribute 'float'")
        elif isinstance(node, ast.Constant) and type(node.value) is float:
            offences.append(f"{module.name}:{node.lineno} contains a float literal")
    return offences


@pytest.mark.parametrize("module", scanned_modules(), ids=lambda path: path.name)
def test_module_contains_no_float(module: Path) -> None:
    assert float_offences(module) == []


def test_the_scan_covers_both_group_a_source_trees() -> None:
    scanned = {path.parent.name for path in scanned_modules()}
    assert {"types", "core"} <= scanned


def test_the_detector_recognises_a_float_annotation(tmp_path: Path) -> None:
    # Arrange — a module the scan must reject, so a passing suite is not a vacuous one.
    offending = tmp_path / "offending.py"
    offending.write_text("def nav() -> float:\n    return float(1.5)\n", encoding="utf-8")
    # Act / Assert
    assert len(float_offences(offending)) == 3
