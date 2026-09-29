"""Read-only injected-seam coverage for the doctor operator surface."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from squatch.config import load
from squatch.doctor import CHECK_NAMES, DETAIL_LIMIT, Doctor, probe_lock
from squatch.lockfile import Lockfile


class Process:
    def __init__(self, *, rc=0, out="git version test\n", err=""):
        self.result = rc, out, err
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, **kwargs):
        self.calls.append((argv, cwd, env, timeout))
        return self.result


def doctor(tmp_path, *, process=None, config_loader=None, lock_probe=None, journal_reader=None,
           interpreter=None, prefix=None, env=None):
    repo = tmp_path / "repo"
    venv = repo / ".venv"
    (venv / "bin").mkdir(parents=True)
    return Doctor(
        repo=repo, config_path=None, process=process or Process(),
        env=env if env is not None else {"PATH": "test"},
        interpreter=interpreter or venv / "bin" / "python", prefix=prefix or venv,
        config_loader=config_loader or (lambda *_args, **_kwargs: SimpleNamespace(state_dir=Path("state"))),
        lock_probe=lock_probe or (lambda _state: "available"),
        journal_reader=journal_reader or (lambda _state: iter(())))


def test_doctor_runs_the_five_ordered_read_checks_and_renders_exactly(tmp_path):
    process = Process()
    value = doctor(tmp_path, process=process)
    report = asyncio.run(value.run())
    assert tuple(check.name for check in report.checks) == CHECK_NAMES
    assert report.render() == (
        "doctor: ok\nPASS venv: checkout .venv\nPASS git: git version test\n"
        "PASS config: loaded\nPASS lock: available\nPASS journal: 0 record(s) readable\n")
    assert process.calls == [(["git", "-C", str(value._repo), "--version"],
                             value._repo, {"PATH": "test"}, 60)]
    assert report.exit_code == 0


def test_doctor_bounds_each_exception_and_checks_everything(tmp_path):
    long = "x" * (DETAIL_LIMIT * 2)
    value = doctor(
        tmp_path, process=Process(rc=1, err=long), prefix=tmp_path / "outside",
        config_loader=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError(long)),
        lock_probe=lambda _state: (_ for _ in ()).throw(RuntimeError(long)),
        journal_reader=lambda _state: (_ for _ in ()).throw(OSError(long)))
    report = asyncio.run(value.run())
    assert not report.ok and tuple(c.name for c in report.checks) == CHECK_NAMES
    assert all(len(c.detail) <= DETAIL_LIMIT and "\n" not in c.detail for c in report.checks)
    assert report.render().startswith("doctor: failed\nFAIL venv:")
    assert report.exit_code == 2


def test_venv_uses_prefix_when_venv_executable_is_a_symlink(tmp_path):
    value = doctor(tmp_path, interpreter=tmp_path / "repo/.venv/bin/python",
                   prefix=tmp_path / "repo/.venv")
    shared = tmp_path / "shared-python"
    shared.touch()
    (tmp_path / "repo/.venv/bin/python").symlink_to(shared)
    assert asyncio.run(value.run()).checks[0].passed


def test_doctor_has_only_read_seams(tmp_path):
    calls = []
    def config_loader(*_args, **_kwargs):
        calls.append("config")
        return SimpleNamespace(state_dir=Path("state"))
    value = doctor(tmp_path, config_loader=config_loader,
                   lock_probe=lambda state: calls.append(("lock", state)) or "available",
                   journal_reader=lambda state: calls.append(("journal", state)) or iter(()))
    assert asyncio.run(value.run()).ok
    assert calls == ["config", "config", "config", ("lock", value._repo / "state"), "config",
                     ("journal", value._repo / "state")]


@pytest.mark.parametrize("valid_config", [True, False])
def test_git_probe_never_inherits_provider_credentials(tmp_path, valid_config):
    process = Process()
    env = {"PATH": "/usr/bin", "HOME": "/operator", "CUSTOM_PROVIDER_KEY": "secret"}
    value = doctor(tmp_path, process=process, config_loader=load, env=env)
    config = value._repo / "config.yaml"
    config.write_text("""schema_version: 1
state_dir: state
routing: []
providers:
  - name: custom
    kind: cli
    auth: CUSTOM_PROVIDER_KEY
    models_by_tier: {low: test, medium: test, high: test, max: test}
    limits: {concurrency: 1}
""" if valid_config else "schema_version: invalid\n")

    report = asyncio.run(value.run())

    assert tuple(c.name for c in report.checks) == CHECK_NAMES
    assert report.checks[1].passed
    assert report.checks[2].passed is valid_config
    [(_, _, received, _)] = process.calls
    assert "CUSTOM_PROVIDER_KEY" not in received
    assert received == ({"PATH": "/usr/bin", "HOME": "/operator"}
                        if valid_config else {"PATH": "/usr/bin"})
    assert env["CUSTOM_PROVIDER_KEY"] == "secret"


def _snapshot(root: Path):
    if not root.exists():
        return None
    return tuple((path.relative_to(root).as_posix(),
                  path.read_bytes() if path.is_file() else None)
                 for path in sorted(root.rglob("*")))


def test_real_lock_probe_is_read_only_for_missing_free_and_live_lock(tmp_path):
    state = tmp_path / "state"
    assert probe_lock(state) == "available"
    assert not state.exists()

    lock = Lockfile(
        state, instance_id="doctor-test",
        clock=lambda: datetime(2026, 9, 29, tzinfo=UTC))
    lock.acquire()
    try:
        before = _snapshot(state)
        assert probe_lock(state) == "held by doctor-test"
        assert _snapshot(state) == before
    finally:
        lock.release()

    before = _snapshot(state)
    assert probe_lock(state) == "available"
    assert _snapshot(state) == before


def test_default_journal_reader_checks_active_and_rolled_records_without_writing(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".venv/bin").mkdir(parents=True)
    journal_dir = repo / "state/journal"
    journal_dir.mkdir(parents=True)
    for sequence in (1, 2):
        event = {
            "v": 1, "type": "signal", "ts": "2026-09-29T12:00:00+00:00",
            "ticket": None, "key": None, "body": {"sequence": sequence},
        }
        (journal_dir / f"{sequence:06d}-20260929.jsonl").write_text(
            json.dumps(event) + "\n")
    before = _snapshot(repo)

    value = Doctor(
        repo=repo, config_path=None, process=Process(), env={"PATH": "test"},
        prefix=repo / ".venv",
        config_loader=lambda *_args, **_kwargs: SimpleNamespace(state_dir=Path("state")))
    report = asyncio.run(value.run())

    assert report.ok
    assert report.checks[-1].detail == "2 record(s) readable"
    assert _snapshot(repo) == before


@pytest.mark.parametrize("failed", ["git", "lock", "journal"])
def test_probe_exception_does_not_skip_later_checks(tmp_path, failed):
    calls = []

    def probe(name, result):
        calls.append(name)
        if name == failed:
            raise OSError("unavailable\n" + "x" * 300)
        return result

    class RaisingProcess(Process):
        async def run(self, *args, **kwargs):
            probe("git", None)
            return await super().run(*args, **kwargs)

    value = doctor(
        tmp_path, process=RaisingProcess(),
        lock_probe=lambda _state: probe("lock", "available"),
        journal_reader=lambda _state: probe("journal", iter(())))
    report = asyncio.run(value.run())

    assert calls == ["git", "lock", "journal"]
    assert [check.name for check in report.checks if not check.passed] == [failed]
    assert all(len(check.detail) <= DETAIL_LIMIT and "\n" not in check.detail
               for check in report.checks)
    assert report.exit_code == 2


def test_live_lock_with_unparseable_record_fails_without_writing(tmp_path):
    state = tmp_path / "state"
    lock = Lockfile(state, instance_id="live", clock=lambda: datetime(2026, 9, 29, tzinfo=UTC))
    lock.acquire()
    try:
        lock.path.write_bytes(b"not json")
        before = _snapshot(state)
        with pytest.raises(RuntimeError, match="live lock holder record is not parseable"):
            probe_lock(state)
        assert _snapshot(state) == before
    finally:
        lock.release()
