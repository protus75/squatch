"""Direct proofs for per-dispatch configuration capture."""

import copy
import asyncio
from pathlib import Path

import pytest
import yaml

from squatch.config import Config, load, parse, snapshot
from squatch.daemon import DispatchAdmission


VALID = {
    "schema_version": 1,
    "state_dir": "state",
    "providers": [{
        "name": "provider", "kind": "cli",
        "models_by_tier": {"low": "low", "medium": "medium", "high": "high", "max": "max"},
        "limits": {"concurrency": 1},
    }],
    "routing": [{"tier": "medium", "surface": "implement",
                 "candidates": [{"provider": "provider", "model": "old"}]}],
    "review": {"mechanical": [{"code": "TEST", "argv": ["pytest"],
                                  "trigger": ["squatch/"], "severity": "hard"}],
               "trigger_map": {"squatch/": ["TEST"]}},
}


def config(*, model: str = "old") -> Config:
    data = copy.deepcopy(VALID)
    data["routing"][0]["candidates"][0]["model"] = model
    return parse(data, source="test")


@pytest.mark.parametrize("factory", ["parse", "load"])
def test_snapshot_deeply_detaches_validated_config(factory: str, tmp_path: Path):
    if factory == "parse":
        source = config()
    else:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(VALID))
        source = load(cwd=tmp_path)
    captured = snapshot(source)

    source.providers[0].limits.concurrency = 2
    source.routing[0].candidates[0].model = "source"
    source.review.mechanical[0].argv.append("-q")
    source.review.trigger_map["squatch/"].append("SOURCE")
    assert captured.providers[0].limits.concurrency == 1
    assert captured.routing[0].candidates[0].model == "old"
    assert captured.review.mechanical[0].argv == ["pytest"]
    assert captured.review.trigger_map == {"squatch/": ["TEST"]}

    captured.providers[0].limits.concurrency = 3
    captured.routing[0].candidates[0].model = "captured"
    captured.review.mechanical[0].argv.append("--quiet")
    captured.review.trigger_map["squatch/"].append("CAPTURED")
    assert source.providers[0].limits.concurrency == 2
    assert source.routing[0].candidates[0].model == "source"
    assert source.review.mechanical[0].argv == ["pytest", "-q"]
    assert source.review.trigger_map == {"squatch/": ["TEST", "SOURCE"]}


@pytest.mark.asyncio
async def test_admission_captures_one_config_per_accepted_offer():
    current = config(model="first")
    supplier_calls = 0
    started = asyncio.Event()
    release = asyncio.Event()
    received: list[Config] = []
    work_calls: list[str] = []

    def supplier() -> Config:
        nonlocal supplier_calls
        supplier_calls += 1
        return current

    async def work(stem: str, captured: Config) -> str:
        work_calls.append(stem)
        received.append(captured)
        if stem == "first":
            started.set()
            await release.wait()
            assert captured.routing[0].candidates[0].model == "first"
        return captured.routing[0].candidates[0].model or ""

    admission = DispatchAdmission(supplier)
    first = admission.admit("first", work)
    assert first is not None
    assert admission.admit("busy", work) is None
    assert supplier_calls == 1 and work_calls == []
    await started.wait()
    current.routing[0].candidates[0].model = "changed-source"
    release.set()
    assert await first == "first"

    current = config(model="second")
    second = admission.admit("second", work)
    assert second is not None
    assert await second == "second"
    assert supplier_calls == 2
    assert work_calls == ["first", "second"]
    assert received[0] is not received[1]


@pytest.mark.asyncio
async def test_config_capture_failures_start_no_work_and_leave_admission_open(monkeypatch):
    calls: list[str] = []
    supplier_error: RuntimeError | None = RuntimeError("supplier failure")

    async def work(stem: str, captured: Config) -> str:
        calls.append(stem)
        return stem

    def supplier_failure() -> Config:
        if supplier_error is not None:
            raise supplier_error
        return config()

    admission = DispatchAdmission(supplier_failure)
    with pytest.raises(RuntimeError, match="supplier failure"):
        admission.admit("failed", work)
    assert calls == []

    supplier_error = None
    accepted = admission.admit("later-after-supplier", work)
    assert accepted is not None
    assert await accepted == "later-after-supplier"

    admission = DispatchAdmission(config)
    def snapshot_failure(captured: Config) -> Config:
        raise RuntimeError("snapshot failure")
    monkeypatch.setattr("squatch.daemon.snapshot", snapshot_failure)
    with pytest.raises(RuntimeError, match="snapshot failure"):
        admission.admit("failed", work)
    assert calls == ["later-after-supplier"]

    monkeypatch.setattr("squatch.daemon.snapshot", snapshot)
    accepted = admission.admit("later", work)
    assert accepted is not None
    assert await accepted == "later"
    assert calls == ["later-after-supplier", "later"]
