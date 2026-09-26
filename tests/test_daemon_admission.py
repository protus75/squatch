"""Direct proofs for dormant daemon dispatch admission."""

import ast
import asyncio
from pathlib import Path

import pytest

from squatch.daemon import DispatchAdmission


@pytest.mark.asyncio
async def test_admission_reserves_before_work_can_yield_and_refuses_busy_offer():
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []
    active = 0
    maximum_active = 0

    async def work(stem: str) -> str:
        nonlocal active, maximum_active
        calls.append(stem)
        active += 1
        maximum_active = max(maximum_active, active)
        started.set()
        await release.wait()
        active -= 1
        return stem

    admission = DispatchAdmission()
    first = admission.admit("first", work)
    assert first is not None
    assert admission.admit("second", work) is None
    assert calls == []

    await started.wait()
    assert calls == ["first"]
    assert maximum_active == 1
    release.set()
    assert await first == "first"


@pytest.mark.asyncio
async def test_slot_lasts_until_a_completed_outcome_is_observed():
    completed = asyncio.Event()
    rejected_calls: list[str] = []

    async def work(stem: str) -> str:
        return stem

    async def rejected_work(stem: str) -> None:
        rejected_calls.append(stem)

    admission = DispatchAdmission()
    first = admission.admit("first", work)
    assert first is not None
    first.add_done_callback(lambda task: completed.set())
    await completed.wait()

    assert admission.admit("second", rejected_work) is None
    assert rejected_calls == []
    assert await first == "first"

    second = admission.admit("second", work)
    assert second is not None
    assert await second == "second"


@pytest.mark.asyncio
async def test_failure_and_cancellation_release_after_their_outcomes_are_observed():
    admission = DispatchAdmission()

    async def failed_work(stem: str) -> None:
        raise ValueError(stem)

    failed = admission.admit("failed", failed_work)
    assert failed is not None
    with pytest.raises(ValueError, match="failed"):
        await failed

    started = asyncio.Event()
    async def blocked_work(stem: str) -> None:
        started.set()
        await asyncio.Event().wait()

    cancelled = admission.admit("cancelled", blocked_work)
    assert cancelled is not None
    await started.wait()
    assert cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled

    async def success(stem: str) -> str:
        return stem

    next_task = admission.admit("next", success)
    assert next_task is not None
    assert await next_task == "next"


@pytest.mark.asyncio
async def test_cancellation_before_work_starts_releases_without_calling_work():
    admission = DispatchAdmission()
    calls: list[str] = []

    async def work(stem: str) -> None:
        calls.append(stem)

    cancelled = admission.admit("never-started", work)
    assert cancelled is not None
    assert cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    assert calls == []

    replacement = admission.admit("replacement", work)
    assert replacement is not None
    assert await replacement is None


def _local_import_closure(root: Path, package: str = "squatch") -> set[str]:
    """Follow local absolute package imports from the module entry point."""
    package_root = root / package

    def source(module: str) -> Path | None:
        relative = module.removeprefix(f"{package}.").replace(".", "/")
        candidates = (package_root / f"{relative}.py", package_root / relative / "__init__.py")
        return next((path for path in candidates if path.is_file()), None)

    reachable: set[str] = set()
    pending = [f"{package}.__main__"]
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        path = source(module)
        if path is None:
            continue
        reachable.add(module)
        tree = ast.parse(path.read_text(), filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names if alias.name.startswith(f"{package}."))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == package:
                    imports.update(f"{package}.{alias.name}" for alias in node.names)
                elif node.module.startswith(f"{package}."):
                    imports.add(node.module)
        pending.extend(sorted(imports - reachable))
    return reachable


def _assert_daemon_unreachable(root: Path) -> None:
    assert "squatch.daemon" not in _local_import_closure(root)


def test_dormancy_scan_recognizes_import_forms_and_fixture_daemon_edge(tmp_path: Path):
    package = tmp_path / "squatch"
    package.mkdir()
    for name, text in {
        "__init__.py": "",
        "__main__.py": "import squatch.imported\n",
        "imported.py": "from squatch import package_import\n",
        "package_import.py": "from squatch.target import Item\n",
        "target.py": "",
        "daemon.py": "",
    }.items():
        (package / name).write_text(text)

    assert "squatch.target" in _local_import_closure(tmp_path)
    _assert_daemon_unreachable(tmp_path)

    (package / "target.py").write_text("import squatch.daemon\n")
    with pytest.raises(AssertionError):
        _assert_daemon_unreachable(tmp_path)
