"""Direct proofs for dormant Phase 3 scheduling construction."""

import ast
import asyncio
from pathlib import Path

import pytest

from squatch.scheduler import Scheduler
from squatch.watcher import Watcher


@pytest.mark.asyncio
async def test_latest_offer_keeps_one_blocked_dispatch_and_then_uses_its_priority():
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []
    active = 0
    maximum_active = 0

    async def dispatch(stem: str) -> None:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        calls.append(stem)
        if stem == "first":
            started.set()
            await release.wait()
        active -= 1

    scheduler = Scheduler(dispatch)
    scheduler.offer(("first", "stale"))
    await started.wait()
    scheduler.offer(("first", "low", "high"))
    scheduler.offer(("first", "highest", "low"))
    release.set()
    await scheduler.join()

    assert calls == ["first", "highest", "low"]
    assert maximum_active == 1


@pytest.mark.asyncio
async def test_watcher_burst_converges_on_final_snapshot_without_a_second_dispatcher():
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []
    active = 0
    maximum_active = 0

    async def dispatch(stem: str) -> None:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        calls.append(stem)
        if stem == "running":
            started.set()
            await release.wait()
        active -= 1

    scheduler = Scheduler(dispatch)
    watcher = Watcher(scheduler)
    watcher.observed(("running", "old"))
    await started.wait()
    watcher.observed(("running", "middle"))
    watcher.observed(("running", "final-first", "final-second"))
    release.set()
    await scheduler.join()

    assert calls == ["running", "final-first", "final-second"]
    assert maximum_active == 1


def _local_import_closure(root: Path, package: str = "squatch") -> set[str]:
    """Follow local absolute ``squatch.*`` imports from a package module."""
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


def test_dormancy_scan_follows_indirect_absolute_import_forms(tmp_path: Path):
    package = tmp_path / "squatch"
    package.mkdir()
    for name, text in {
        "__init__.py": "",
        "__main__.py": "import squatch.bridge\n",
        "bridge.py": "from squatch import scheduler\n",
        "scheduler.py": "",
        "watcher.py": "",
    }.items():
        (package / name).write_text(text)
    assert "squatch.scheduler" in _local_import_closure(tmp_path)

    (package / "bridge.py").write_text("from squatch.watcher import Watcher\n")
    assert "squatch.watcher" in _local_import_closure(tmp_path)


def test_scheduler_and_watcher_are_unreachable_from_the_production_root():
    root = Path(__file__).resolve().parents[1]
    reachable = _local_import_closure(root)
    assert "squatch.scheduler" not in reachable
    assert "squatch.watcher" not in reachable
