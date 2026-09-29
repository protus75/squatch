"""Read-only mechanical diagnostics for the operator CLI."""

import asyncio
import fcntl
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from squatch.config import load
from squatch.git import Git
from squatch.journal import read_events
from squatch.lockfile import Holder, LOCK_NAME
from squatch.providers import child_env
from squatch.seams import ProcessExec

DETAIL_LIMIT = 240
CHECK_NAMES = ("venv", "git", "config", "lock", "journal")


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Report:
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 2

    def render(self) -> str:
        lines = [f"doctor: {'ok' if self.ok else 'failed'}"]
        lines.extend(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}"
                     for check in self.checks)
        return "\n".join(lines) + "\n"


def _detail(value: object) -> str:
    """Keep diagnostics single-line and bounded before they reach the CLI."""
    text = " ".join(str(value).split()) or "unspecified failure"
    return text[:DETAIL_LIMIT]


def probe_lock(state_dir: Path) -> str:
    """Inspect a lock without creating its directory, file, or record."""
    path = Path(state_dir) / LOCK_NAME
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return "available"
    try:
        try:
            # A shared probe distinguishes a live exclusive holder without
            # claiming the engine's writer lock or changing its record.
            # A racing writer can briefly refuse until this probe unlocks;
            # accepting that race avoids trusting a stale holder record.
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                holder = Holder(**json.loads(os.read(fd, 65536)))
            except (TypeError, ValueError):
                raise RuntimeError("live lock holder record is not parseable") from None
            return f"held by {holder.instance_id}"
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return "available"
    finally:
        os.close(fd)


class Doctor:
    """The fixed, provider-free ordered check set over injected read seams."""

    def __init__(self, *, repo: Path, config_path: Path | None, process: ProcessExec,
                 env: Mapping[str, str], interpreter: str | Path = sys.executable,
                 prefix: str | Path = sys.prefix,
                 config_loader: Callable[..., object] = load,
                 lock_probe: Callable[[Path], str] = probe_lock,
                 journal_reader: Callable[[Path], object] = read_events):
        self._repo = Path(repo)
        self._config_path = config_path
        self._process = process
        self._env = dict(env)
        self._interpreter = Path(interpreter)
        self._prefix = Path(prefix)
        self._config_loader = config_loader
        self._lock_probe = lock_probe
        self._journal_reader = journal_reader

    async def run(self) -> Report:
        checks = []
        for name, action in (("venv", self._venv), ("git", self._git),
                             ("config", self._config), ("lock", self._lock),
                             ("journal", self._journal)):
            checks.append(await self._check(name, action))
        return Report(tuple(checks))

    async def _check(self, name: str, action: Callable[[], object]) -> Check:
        try:
            result = action()
            if asyncio.iscoroutine(result):
                result = await result
            return Check(name, True, _detail(result))
        except Exception as error:
            return Check(name, False, _detail(f"{type(error).__name__}: {error}"))

    def _venv(self) -> str:
        # sys.executable can be a venv-local symlink to a shared interpreter;
        # sys.prefix retains the venv identity and is therefore the authority.
        expected = (self._repo / ".venv").resolve()
        actual = self._prefix.resolve()
        if actual != expected:
            raise RuntimeError(f"interpreter prefix {actual} is not checkout .venv {expected}")
        return "checkout .venv"

    async def _git(self) -> str:
        try:
            config = self._config_loader(self._config_path, cwd=self._repo)
            env = child_env(self._env, {p.auth for p in config.providers if p.auth})
        except Exception:
            # A broken config cannot identify its secrets. Version discovery
            # needs only executable lookup, never the operator's credentials.
            env = {name: self._env[name] for name in ("PATH",) if name in self._env}
        git = Git(self._process, env=env, timeout=60)
        # The existing argv wrapper also owns this repository-free probe;
        # no second Git executor or repository operation is needed.
        out = await git._run(self._repo, "--version")
        return out.strip() or "git answered"

    def _config(self) -> str:
        self._config_loader(self._config_path, cwd=self._repo)
        return "loaded"

    def _lock(self) -> str:
        return self._lock_probe(self._repo / self._state_dir())

    def _journal(self) -> str:
        count = sum(1 for _ in self._journal_reader(self._repo / self._state_dir()))
        return f"{count} record(s) readable"

    def _state_dir(self) -> Path:
        return self._config_loader(self._config_path, cwd=self._repo).state_dir
