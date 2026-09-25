"""Harness proof: the package imports and the project metadata matches the plan.

Every later pytest gate runs on this harness (SQUATCH_PLAN.md section 0,
Phase 0 deliverable 2), so it must be green before any engine logic lands.
"""

import re
import sys
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _dep_name(spec: str) -> str:
    # PEP 503 normalization of the name that leads a requirement spec.
    name = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec).group(0)
    return re.sub(r"[-_.]+", "-", name).lower()


def _project() -> dict:
    return tomllib.loads(PYPROJECT.read_text())["project"]


def test_package_imports():
    import squatch  # noqa: F401


def test_interpreter_meets_floor():
    # D1: the squatch venv pins Python 3.14+; a lower interpreter is refused.
    assert sys.version_info >= (3, 14)


def test_pyproject_pins_python_floor():
    assert _project()["requires-python"] == ">=3.14"


def test_pyproject_declares_runtime_deps():
    declared = {_dep_name(d) for d in _project()["dependencies"]}
    assert {"pyyaml", "pydantic"} <= declared
