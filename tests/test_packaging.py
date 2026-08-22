"""Every module a console script imports must actually ship in the wheel.

Guards the 0.1.0 failure: the entry points pointed at ``cli:app`` while
``[tool.poetry] packages`` listed only ``aws_scanner_lib`` and
``services``, so the installed command died on ``ModuleNotFoundError``.
Nothing in the suite caught it, because inside the repo ``cli`` imports
fine from the working directory.

This reads the declarations rather than building, so it is fast and runs
locally. The wheel is separately built, installed and executed by the
``package`` job in .github/workflows/ci.yml.
"""

import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _pyproject() -> dict[str, Any]:
    with PYPROJECT.open("rb") as handle:
        parsed: dict[str, Any] = tomllib.load(handle)
    return parsed


def _packaged_names() -> set[str]:
    """Top-level importable names the build backend is told to include."""
    includes = _pyproject()["tool"]["poetry"]["packages"]
    return {Path(entry["include"]).stem for entry in includes}


def _entry_point_modules() -> dict[str, str]:
    """Console script name -> the top-level module it imports."""
    scripts = _pyproject()["project"]["scripts"]
    return {
        name: target.split(":")[0].split(".")[0] for name, target in scripts.items()
    }


def test_every_console_script_module_is_packaged() -> None:
    packaged = _packaged_names()
    missing = {
        script: module
        for script, module in _entry_point_modules().items()
        if module not in packaged
    }
    assert not missing, (
        f"console scripts import modules that the wheel will not contain: {missing}. "
        f"Packaged names: {sorted(packaged)}. Add the module to [tool.poetry] packages."
    )


def test_wheel_claims_exactly_one_top_level_name() -> None:
    """ADR-0004: the wheel installs one name into site-packages.

    Generic top-level names like `cli` or `services` can shadow a user's
    own modules when pip-installed into a shared virtualenv, so adding a
    second entry here has to be a deliberate, reviewed act.
    """
    assert _packaged_names() == {"aws_resource_inventory"}, (
        f"the wheel would claim {sorted(_packaged_names())} in site-packages; "
        "everything belongs inside aws_resource_inventory/ (docs/adr/0004)."
    )


def test_packaged_names_exist_on_disk() -> None:
    """A stale entry in `packages` silently drops from the wheel."""
    root = PYPROJECT.parent
    missing = [
        name
        for name in _packaged_names()
        if not (root / name).is_dir() and not (root / f"{name}.py").is_file()
    ]
    assert not missing, f"[tool.poetry] packages names nothing on disk: {missing}"


@pytest.mark.parametrize("module", sorted(set(_entry_point_modules().values())))
def test_entry_point_module_is_importable(module: str) -> None:
    """The module named by an entry point must import without side effects."""
    __import__(module)
    assert module in sys.modules
