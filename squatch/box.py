"""The durable Suggestion Box queue (SQUATCH_PLAN.md section 12)."""

import argparse
import asyncio
import contextvars
import hashlib
import os
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from squatch.config import ConfigError, load
from squatch.git import Git, GitError
from squatch.journal import Journal, render_ts
from squatch.lockfile import LockHeld, Lockfile
from squatch.providers import child_env
from squatch.seams import Clock, Filesystem, LocalFilesystem, SubprocessExec

SCHEMA_VERSION = 1
MESSAGE_CLASSES = frozenset(
    {"suggestion", "failure_report", "override_report", "retro_finding", "bug_report"})
STATUSES = frozenset({"pending", "authored", "tombstoned", "decided"})
BOOTSTRAP_ORIGIN = "bootstrap-ingest"
STORM_BREAKER_ORIGIN = "storm-breaker:"

MessageClass = Literal[
    "suggestion", "failure_report", "override_report", "retro_finding", "bug_report"]
Status = Literal["pending", "authored", "tombstoned", "decided"]
BugOrigin = Literal["self_diagnosed", "player"]
OccurrenceRecorder = Callable[..., bool]
RereportCallback = Callable[["Message"], None]

REREPORT_REOPEN_THRESHOLD = 3
REREPORT_PAVED_ROAD = "rerun through a journal-backed Squatch command"

_SIGNATURE = re.compile(r"\A[0-9a-f]{64}\Z")
_BOX_ID = re.compile(r"\Abox-(\d{6})-([0-9a-f]{8})\Z")
_FILE = re.compile(r"\A(\d{6})-([0-9a-f]{8})\.json\Z")
_LIST_MARKER = re.compile(r"\A(?:[-*]|\d+\.)\s+")
_DIGITS = re.compile(r"\d+")


class BoxCorruption(ValueError):
    """A malformed or unreadable durable box record; readers never skip it."""


class RereportCallbackRequired(RuntimeError):
    """A tombstone reached its reopen threshold without a journal writer."""

    paved_road = REREPORT_PAVED_ROAD


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    link: str = Field(min_length=1)
    note: str = Field(min_length=1)
    resolved_at: str


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    id: str
    seq: int = Field(ge=1)
    signature: str
    message_class: MessageClass
    summary: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    origin: str = Field(min_length=1)
    bug_origin: BugOrigin | None = None
    has_repro: StrictBool | None = None
    stage: str | None = None
    outcome: str | None = None
    run_seq: int | None = Field(default=None, ge=0)
    enqueued_at: str
    status: Status = "pending"
    resolution: Resolution | None = None
    triage: dict | None = None
    reports: int = Field(default=1, ge=1)
    reopened_from_tombstone: StrictBool = False
    pending_threshold_reopen: StrictBool = False
    rereport_ids: tuple[str, ...] = ()
    retro_report_key: str | None = None
    fixed_failure: str | None = None
    overcorrection_risk: str | None = None
    proposed_spec_paths: tuple[str, ...] | None = None

    @field_validator("signature")
    @classmethod
    def _valid_signature(cls, value: str) -> str:
        if not _SIGNATURE.match(value):
            raise ValueError("signature must be 64 lowercase hexadecimal characters")
        return value

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _BOX_ID.match(value):
            raise ValueError("id must be box-<six digit seq>-<sig8>")
        return value

    @model_validator(mode="after")
    def _bug_policy_inputs_match_class(self):
        supplied = self.bug_origin is not None or self.has_repro is not None
        if self.message_class == "bug_report":
            if self.bug_origin is None or self.has_repro is None:
                raise ValueError("bug_report requires bug_origin and has_repro")
        elif supplied:
            raise ValueError("bug_origin and has_repro are allowed only on bug_report")
        retro = (self.retro_report_key, self.fixed_failure, self.overcorrection_risk,
                 self.proposed_spec_paths)
        if self.message_class == "retro_finding":
            if (any(value is None for value in retro)
                    or not all(isinstance(value, str) and value for value in retro[:3])
                    or not self.proposed_spec_paths):
                raise ValueError("retro_finding requires complete retro proposal provenance")
        elif any(value is not None for value in retro):
            raise ValueError("retro proposal provenance is allowed only on retro_finding")
        return self


@dataclass(frozen=True)
class Enqueued:
    id: str
    duplicate: bool


@dataclass(frozen=True)
class Ingested:
    filed: int
    duplicates: int


@dataclass(frozen=True)
class _OccurrenceBinding:
    state_dir: Path
    recorder: OccurrenceRecorder


_occurrence_binding: contextvars.ContextVar[_OccurrenceBinding | None] = contextvars.ContextVar(
    "box_occurrence_binding", default=None)


@contextmanager
def scoped_occurrence_recorder(*, state_dir: Path, recorder: OccurrenceRecorder) -> Iterator[None]:
    """Bind a recorder only for Boxes over this state directory in this context."""
    binding = _OccurrenceBinding(Path(state_dir).resolve(), recorder)
    token = _occurrence_binding.set(binding)
    try:
        yield
    finally:
        _occurrence_binding.reset(token)


def _normalized(reason: str) -> str:
    tokens = (_DIGITS.sub("", token) for token in reason.split() if "/" not in token)
    return " ".join(token for token in tokens if token).strip()


def signature(message_class: str, origin: str, stage: str | None, outcome: str | None,
              reason: str) -> str:
    fields = (message_class, origin, stage or "", outcome or "", _normalized(reason))
    return hashlib.sha256("\n".join(fields).encode()).hexdigest()


class Box:
    def __init__(self, state_dir: Path, *, fs: Filesystem, clock: Clock,
                 occurrence_recorder: OccurrenceRecorder | None = None,
                 rereport_callback: RereportCallback | None = None):
        self._state_dir = Path(state_dir).resolve()
        self.dir = self._state_dir / "box"
        self._fs = fs
        self._clock = clock
        self._occurrence_recorder = occurrence_recorder
        self._rereport_callback = rereport_callback

    def _records(self) -> list[tuple[Path, Message]]:
        if not self.dir.is_dir():
            return []
        records: list[tuple[Path, Message]] = []
        for path in sorted(self.dir.glob("*.json")):
            match = _FILE.match(path.name)
            if match is None:
                raise BoxCorruption(f"{path}: not a box message filename")
            try:
                message = Message.model_validate_json(path.read_text())
            except Exception as e:
                raise BoxCorruption(f"{path}: invalid box message: {e}") from e
            if (message.seq != int(match.group(1))
                    or message.signature[:8] != match.group(2)
                    or message.id != f"box-{match.group(1)}-{match.group(2)}"):
                raise BoxCorruption(f"{path}: filename and message identity disagree")
            records.append((path, message))
        return records

    def enqueue(self, *, message_class: str, summary: str, detail: str, origin: str,
                stage: str | None = None, outcome: str | None = None,
                run_seq: int | None = None, bug_origin: BugOrigin | None = None,
                has_repro: bool | None = None, retro_report_key: str | None = None,
                fixed_failure: str | None = None, overcorrection_risk: str | None = None,
                proposed_spec_paths: tuple[str, ...] | None = None) -> Enqueued:
        sig = signature(message_class, origin, stage, outcome, detail)
        records = self._records()
        duplicate = next(((path, message) for path, message in records
                          if message.signature == sig), None)
        if duplicate is not None:
            _, message = duplicate
            self.record_rereport(message.id)
            return Enqueued(message.id, True)
        seq = max((message.seq for _, message in records), default=0) + 1
        sig8 = sig[:8]
        path = self.dir / f"{seq:06d}-{sig8}.json"
        if path.exists():
            raise FileExistsError(f"refusing to overwrite box message {path}")
        message = Message(
            id=f"box-{seq:06d}-{sig8}", seq=seq, signature=sig,
            message_class=message_class, summary=summary, detail=detail, origin=origin,
            bug_origin=bug_origin, has_repro=has_repro,
            retro_report_key=retro_report_key, fixed_failure=fixed_failure,
            overcorrection_risk=overcorrection_risk,
            proposed_spec_paths=proposed_spec_paths,
            stage=stage, outcome=outcome, run_seq=run_seq,
            enqueued_at=render_ts(self._clock()), status="pending", resolution=None,
            triage=None, reports=1)
        self._fs.write(path, message.model_dump_json(indent=2).encode())
        self._record_occurrence(message)
        return Enqueued(message.id, False)

    def record_rereport(self, id: str, *, incoming_id: str | None = None) -> Message:
        """Count one arrival and reopen a threshold tombstone write-ahead."""
        for path, message in self._records():
            if message.id != id:
                continue
            # Only an explicitly refused reopen retries without incrementing.
            # A semantic arrival's receipt lives in the same atomic replacement
            # as its count, so resolving the incoming message can safely retry.
            if message.pending_threshold_reopen:
                updated = message
            elif incoming_id is not None and incoming_id in message.rereport_ids:
                return message
            else:
                updated = message.model_copy(update={
                    "reports": message.reports + 1,
                    "rereport_ids": (message.rereport_ids + (incoming_id,)
                                     if incoming_id is not None else message.rereport_ids),
                })
            if (message.pending_threshold_reopen
                    or (message.status == "tombstoned"
                        and not message.reopened_from_tombstone
                        and updated.reports >= REREPORT_REOPEN_THRESHOLD)):
                if self._rereport_callback is None:
                    self._replace(path, updated.model_copy(update={
                        "pending_threshold_reopen": True,
                    }))
                    self._record_occurrence(updated)
                    raise RereportCallbackRequired(
                        f"{id} reached the tombstone rereport threshold; "
                        f"paved road: {REREPORT_PAVED_ROAD}")
                self._rereport_callback(updated)
                updated = updated.model_copy(update={
                    "status": "pending", "resolution": None,
                    "reopened_from_tombstone": True,
                    "pending_threshold_reopen": False,
                })
                if (message.pending_threshold_reopen and incoming_id is not None
                        and incoming_id not in message.rereport_ids):
                    updated = updated.model_copy(update={
                        "reports": updated.reports + 1,
                        "rereport_ids": updated.rereport_ids + (incoming_id,),
                    })
            self._replace(path, updated)
            self._record_occurrence(updated)
            return updated
        raise KeyError(id)

    def _record_occurrence(self, message: Message) -> None:
        if message.origin.startswith(STORM_BREAKER_ORIGIN):
            return
        recorder = self._occurrence_recorder
        if recorder is None:
            binding = _occurrence_binding.get()
            if binding is not None and binding.state_dir == self._state_dir:
                recorder = binding.recorder
        if recorder is not None:
            recorder(occurrence_id=f"{message.id}/{message.reports}",
                     signature=message.signature, emitting_stage=message.stage)

    def pending(self) -> list[Message]:
        return [message for _, message in self._records() if message.status == "pending"]

    def by_origin(self, origin: str) -> Message | None:
        """Return the exact-origin record across every durable status."""
        return next((message for _, message in self._records()
                     if message.origin == origin), None)

    def get(self, id: str) -> Message:
        for _, message in self._records():
            if message.id == id:
                return message
        raise KeyError(id)

    def resolve(self, id: str, *, status: str, link: str, note: str) -> Message:
        if status not in STATUSES:
            raise ValueError(f"status {status!r} is not one of {sorted(STATUSES)}")
        if status == "pending":
            raise ValueError("resolution status must be authored, tombstoned, or decided")
        for path, message in self._records():
            if message.id != id:
                continue
            if message.status != "pending":
                raise ValueError(f"message {id} is {message.status}, not pending")
            resolved = message.model_copy(update={
                "status": status,
                "resolution": Resolution(link=link, note=note,
                                         resolved_at=render_ts(self._clock())),
                "reopened_from_tombstone": (
                    False if status == "authored" else message.reopened_from_tombstone),
            })
            self._replace(path, resolved)
            return resolved
        raise KeyError(id)

    def record_triage(self, id: str, triage: dict) -> Message:
        """Persist an Author-bound verdict without resolving the message."""
        for path, message in self._records():
            if message.id != id:
                continue
            if message.status != "pending":
                raise ValueError(f"message {id} is {message.status}, not pending")
            updated = message.model_copy(update={"triage": triage})
            self._replace(path, updated)
            return updated
        raise KeyError(id)

    def _replace(self, path: Path, message: Message) -> None:
        temp = path.with_name(f".{path.name}.replace")
        self._fs.write(temp, message.model_dump_json(indent=2).encode())
        self._fs.replace(temp, path)


def journal_rereport_callback(journal: Journal) -> RereportCallback:
    """Build the one write-ahead tombstone reopen callback."""
    def record(message: Message) -> None:
        key = f"tombstone-reopen/{message.id}/{message.reports}"
        body = {"kind": "tombstone_auto_reopened", "box_id": message.id,
                "signature": message.signature, "reports": message.reports}
        existing = [event for event in journal.read()
                    if event.type == "signal" and event.key == key]
        if existing:
            if any(event.body != body for event in existing):
                raise BoxCorruption(f"journal key {key} conflicts with its rereport body")
            return
        journal.append("signal", body, key=key)
    return record


def enqueue_second_problems(box: Box, run_record: str | Path, *, stem: str, stage: str,
                            outcome: str, run_seq: int) -> list[str]:
    text = Path(run_record).read_text() if isinstance(run_record, Path) else run_record
    inside = False
    ids: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Second problems filed"
            continue
        stripped = line.strip()
        if not inside or _LIST_MARKER.match(stripped) is None:
            continue
        problem = _LIST_MARKER.sub("", stripped, count=1).strip()
        citation = problem.removeprefix("`").removesuffix("`")
        if not problem or _BOX_ID.fullmatch(citation):
            continue
        result = box.enqueue(message_class="suggestion", summary=problem, detail=problem,
                             origin=stem, stage=stage, outcome=outcome, run_seq=run_seq)
        ids.append(result.id)
    return ids


def ingest(box: Box, path: Path) -> Ingested:
    filed = duplicates = 0
    for raw in Path(path).read_text().splitlines():
        if not raw.strip():
            continue
        summary = _LIST_MARKER.sub("", raw.strip()).strip()
        result = box.enqueue(message_class="suggestion", summary=summary, detail=raw,
                             origin=BOOTSTRAP_ORIGIN)
        if result.duplicate:
            duplicates += 1
        else:
            filed += 1
    return Ingested(filed, duplicates)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _instance_checkout(cwd: Path, env: dict[str, str]) -> Path:
    git = Git(SubprocessExec(), env=child_env(env, set()), timeout=60.0)
    common = Path(await git.git_common_dir(cwd))
    if not common.is_absolute():
        common = (cwd / common).resolve()
    if common.name != ".git" or not common.is_dir():
        raise ValueError(f"git common dir {common} does not name a checkout")
    return common.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m squatch.box",
                                     description="Suggestion Box maintenance")
    sub = parser.add_subparsers(dest="verb", required=True)
    command = sub.add_parser("ingest", help="ingest a line-oriented suggestion file")
    command.add_argument("file", type=Path)
    return parser


def main(argv: list[str] | None = None, *, cwd: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    cwd = Path.cwd() if cwd is None else Path(cwd)
    source = args.file if args.file.is_absolute() else cwd / args.file
    if not source.is_file():
        print(f"refused: suggestion source {source} does not exist", file=sys.stderr)
        print("  paved road: pass an existing line-oriented file to `ingest`", file=sys.stderr)
        return 2
    try:
        checkout = asyncio.run(_instance_checkout(cwd, dict(os.environ)))
        config = load(None, cwd=checkout)
    except (GitError, ConfigError, ValueError, OSError) as e:
        print(f"refused: cannot resolve the instance checkout: {e}", file=sys.stderr)
        print("  paved road: run inside the instance checkout or one of its git worktrees",
              file=sys.stderr)
        return 2
    state_dir = checkout / config.state_dir
    lock = Lockfile(state_dir, instance_id="box-ingest", clock=_now)
    try:
        lock.acquire()
    except LockHeld as e:
        print(f"refused: engine holds the instance lock: {e}", file=sys.stderr)
        print("  paved road: wait for the active run or drain to finish, then re-run `ingest`",
              file=sys.stderr)
        return 2
    except OSError as e:
        print(f"refused: cannot ingest into {state_dir / 'box'}: {e}", file=sys.stderr)
        print("  paved road: repair or remove the named corrupt box message, or fix the "
              "state directory permissions, then re-run `ingest`", file=sys.stderr)
        return 2
    try:
        result = ingest(Box(state_dir, fs=LocalFilesystem(), clock=_now), source)
    except RereportCallbackRequired as e:
        print(f"refused: cannot ingest into {state_dir / 'box'}: {e}", file=sys.stderr)
        print(f"  paved road: {REREPORT_PAVED_ROAD}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as e:
        print(f"refused: cannot ingest into {state_dir / 'box'}: {e}", file=sys.stderr)
        print("  paved road: repair or remove the named corrupt box message, or fix the "
              "state directory permissions, then re-run `ingest`", file=sys.stderr)
        return 2
    finally:
        lock.release()
    print(f"filed {result.filed}; duplicates {result.duplicates}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
