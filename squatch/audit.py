"""Pure journal invariant auditor (SQUATCH_PLAN.md sections 6 and 15)."""

import argparse
import asyncio
import os
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from squatch.artifacts import RUN_STATES, TERMINAL_RUN_STATES
from squatch.caps import CAP_NAMES
from squatch.config import ConfigError, load
from squatch.git import Git, GitError
from squatch.journal import EVENT_TYPES, Event, JournalCorruption, read_segments
from squatch.providers import child_env
from squatch.seams import SubprocessExec

Segments = Iterable[Iterable[Event]]


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invariant: str = Field(min_length=1)
    ticket: str | None
    run_seq: int | None
    message: str = Field(min_length=1)


Check = Callable[[Segments], list[Violation]]


@dataclass(frozen=True)
class Invariant:
    name: str
    law: str
    check: Check


def _violation(name: str, event: Event, message: str) -> Violation:
    return Violation(
        invariant=name,
        ticket=event.ticket,
        run_seq=_run_seq(event),
        message=message,
    )


def _run_seq(event: Event) -> int | None:
    run_seq = event.body.get("run_seq")
    return run_seq if type(run_seq) is int else None


def _events(segments: Segments) -> tuple[Event, ...]:
    return tuple(event for segment in segments for event in segment)


def _one_terminal_per_run(segments: Segments) -> list[Violation]:
    name = "one_terminal_per_run"
    running: set[tuple[str | None, object]] = set()
    terminals: dict[tuple[str | None, object], list[Event]] = {}
    for event in _events(segments):
        if event.type != "state_transition":
            continue
        pair = (event.ticket, _run_seq(event))
        state = event.body.get("to")
        if state == "running":
            running.add(pair)
        elif isinstance(state, str) and state in TERMINAL_RUN_STATES and pair in running:
            terminals.setdefault(pair, []).append(event)
    return [
        _violation(name, events[1], "run has more than one terminal state transition")
        for events in terminals.values() if len(events) > 1
    ]


def _declared_caps(segments: Segments) -> list[Violation]:
    name = "declared_caps"
    return [
        _violation(name, event, f"cap {event.body.get('cap')!r} is not declared")
        for event in _events(segments)
        if event.type == "cap_consumed"
        and (not isinstance(event.body.get("cap"), str)
             or event.body.get("cap") not in CAP_NAMES)
    ]


def _effects_paired_at_merged(segments: Segments) -> list[Violation]:
    name = "effects_paired_at_merged"
    active: dict[str | None, object] = {}
    pending: dict[tuple[str | None, object], dict[str | None, list[Event]]] = {}
    violations: list[Violation] = []
    for event in _events(segments):
        if event.type == "state_transition" and event.body.get("to") == "running":
            active[event.ticket] = _run_seq(event)
        pair = (event.ticket, active.get(event.ticket))
        if event.ticket in active and event.type == "effect_intent":
            pending.setdefault(pair, {}).setdefault(event.key, []).append(event)
        elif event.ticket in active and event.type == "effect_completion":
            unmatched = pending.setdefault(pair, {}).setdefault(event.key, [])
            if unmatched:
                unmatched.pop(0)
        if (event.type == "state_transition" and event.body.get("to") == "merged"
                and _run_seq(event) == active.get(event.ticket)):
            for key, unmatched in pending.get(pair, {}).items():
                for intent in unmatched:
                    violations.append(Violation(
                        invariant=name, ticket=intent.ticket,
                        run_seq=pair[1] if isinstance(pair[1], int) else None,
                        message=f"merged run has no effect completion for key {key!r}"))
    return violations


def _merged_carries_commit(segments: Segments) -> list[Violation]:
    name = "merged_carries_commit"
    violations = []
    for event in _events(segments):
        if event.type != "state_transition" or event.body.get("to") != "merged":
            continue
        if "commit" not in event.body:
            violations.append(_violation(name, event, "merged transition has no commit field"))
        elif event.body["commit"] is None and (
                "reviewed_sha" not in event.body or event.body["reviewed_sha"] is not None):
            violations.append(_violation(
                name, event, "null commit requires a null reviewed_sha"))
    return violations


def _closed_run_states(segments: Segments) -> list[Violation]:
    name = "closed_run_states"
    return [
        _violation(name, event, f"run state {event.body.get('to')!r} is not declared")
        for event in _events(segments)
        if event.type == "state_transition"
        and (not isinstance(event.body.get("to"), str)
             or event.body.get("to") not in RUN_STATES)
    ]


def _closed_event_types(segments: Segments) -> list[Violation]:
    name = "closed_event_types"
    return [
        _violation(name, event, f"event type {event.type!r} is not declared")
        for event in _events(segments)
        if not isinstance(event.type, str) or event.type not in EVENT_TYPES
    ]


def _ts_monotone(segments: Segments) -> list[Violation]:
    name = "ts_monotone"
    violations: list[Violation] = []
    for segment in segments:
        previous: Event | None = None
        for event in segment:
            if previous is not None and event.ts < previous.ts:
                violations.append(_violation(
                    name, event, f"timestamp {event.ts!r} precedes {previous.ts!r}"))
            previous = event
    return violations


INVARIANTS = (
    Invariant("one_terminal_per_run", "A run has at most one terminal after it starts.",
              _one_terminal_per_run),
    Invariant("declared_caps", "Every consumed cap belongs to the declared cap vocabulary.",
              _declared_caps),
    Invariant("effects_paired_at_merged",
              "Every effect intent in a merged run has a completion with the same key.",
              _effects_paired_at_merged),
    Invariant("merged_carries_commit",
              "Every merged transition carries its commit or a null no-op settlement pair.",
              _merged_carries_commit),
    Invariant("closed_run_states", "Every transition uses a declared run state.",
              _closed_run_states),
    Invariant("closed_event_types", "Every journal event uses a declared event type.",
              _closed_event_types),
    Invariant("ts_monotone", "Timestamps never decrease within a journal segment.",
              _ts_monotone),
)


def audit(segments: Segments) -> tuple[Violation, ...]:
    materialized = tuple(tuple(segment) for segment in segments)
    return tuple(
        violation
        for invariant in INVARIANTS
        for violation in invariant.check(materialized)
    )


def audit_journal(state_dir: Path) -> tuple[Violation, ...]:
    state_dir = Path(state_dir)
    if not state_dir.is_dir():
        raise FileNotFoundError(f"state directory {state_dir} does not exist")
    journal_dir = state_dir / "journal"
    if not journal_dir.is_dir():
        raise FileNotFoundError(f"journal directory {journal_dir} does not exist")
    return audit(read_segments(state_dir))


async def _instance_checkout(cwd: Path, env: dict[str, str]) -> Path:
    git = Git(SubprocessExec(), env=child_env(env, set()), timeout=60.0)
    common = Path(await git.git_common_dir(cwd))
    if not common.is_absolute():
        common = (cwd / common).resolve()
    if common.name != ".git" or not common.is_dir():
        raise ValueError(f"git common dir {common} does not name a checkout")
    return common.parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m squatch.audit", description="Audit journal invariants")
    parser.add_argument("--state", type=Path, help="instance state directory")
    return parser


def main(argv: list[str] | None = None, *, cwd: Path | None = None) -> int:
    args = _parser().parse_args(argv)
    cwd = Path.cwd() if cwd is None else Path(cwd)
    try:
        if args.state is not None:
            state_dir = args.state if args.state.is_absolute() else cwd / args.state
        else:
            checkout = asyncio.run(_instance_checkout(cwd, dict(os.environ)))
            state_dir = checkout / load(None, cwd=checkout).state_dir
        violations = audit_journal(state_dir)
    except (ConfigError, GitError, JournalCorruption, OSError, ValueError) as error:
        print(f"refused: cannot audit journal: {error}", file=sys.stderr)
        print("  paved road: provide an existing instance state directory and repair any "
              "corruption named above, then re-run the auditor", file=sys.stderr)
        return 2
    for violation in violations:
        print(f"{violation.invariant}: ticket={violation.ticket!r} "
              f"run_seq={violation.run_seq!r}: {violation.message}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
