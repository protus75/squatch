"""Reconcile-on-entry: reap the orphaned in-flight runs an interrupted
predecessor left (SQUATCH_PLAN.md section 11.2; section 18; section 19,
Phase 2).

The writer that just took the single-writer lock is the only writer, and no
daemon exists, so any run the journal still shows in flight is provably
dead: a stem whose last `state_transition` is `running` with no terminal, or
an `effect_intent` with no `effect_completion` after the stem's last
terminal. Phase 2 harvests a present orphan, appends its `abandoned` terminal
through the Journal seam, THEN removes the orphan worktree through git.py (the section
11.2 order: no worktree is wiped before its terminal is journaled). The
terminal frees the stem: the next run takes the next sequence and a fresh
keyspace, and its teardown-and-create clears the branch. Phase 3 moves the
whole step to daemon startup.
"""

import traceback

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from squatch.artifacts import Cost, TERMINAL_RUN_STATES
from squatch.config import Config
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.harvest import extract
from squatch.journal import Event, Journal
from squatch.seams import LocalFilesystem
from squatch.stages import lift_ticket_files
from squatch.tickets import TICKETS_DIR

Report = Callable[[str], None]


@dataclass(frozen=True)
class Orphan:
    stem: str
    run_seq: int
    open_keys: tuple[str, ...]  # intents with no completion in the dead run


def orphans(events: Iterable[Event]) -> list[Orphan]:
    """The in-flight set, folded from the journal in order."""
    running: dict[str, int] = {}
    terminals: dict[str, int] = {}
    open_keys: dict[str, dict[str, None]] = {}
    for e in events:
        stem = e.ticket
        if stem is None:
            continue
        if e.type == "state_transition":
            to = e.body["to"]
            if to == "running":
                running[stem] = e.body["run_seq"]
            elif to in TERMINAL_RUN_STATES:
                running.pop(stem, None)
                terminals[stem] = terminals.get(stem, 0) + 1
                # An intent left open before a terminal is inert history.
                open_keys.pop(stem, None)
        elif e.type == "effect_intent":
            open_keys.setdefault(stem, {})[e.key] = None
        elif e.type == "effect_completion":
            open_keys.get(stem, {}).pop(e.key, None)
    stems = set(running) | {s for s, keys in open_keys.items() if keys}
    return [Orphan(s, running.get(s, terminals.get(s, 0)), tuple(open_keys.get(s, ())))
            for s in sorted(stems)]


async def reconcile(*, repo: Path, config: Config, git: Git, journal: Journal,
                    log: EngineLog, report: Report) -> list[Orphan]:
    """Reap every orphan; the caller holds the writer lock."""
    found = orphans(journal.read())
    for o in found:
        path = repo / config.worktree_root / o.stem
        present = path.exists()
        attempt = f"{TICKETS_DIR}/{o.stem}/attempts/{o.run_seq}"
        harvested = None
        harvest_error = None
        if present:
            try:
                base = _workspace_base(journal.read(), o)
                files = await extract(
                    repo=repo, state_dir=repo / config.state_dir, git=git, stem=o.stem,
                    run_seq=o.run_seq, worktree=path, base=base, outcome="abandoned",
                    stage="reconcile", reason="orphan reaped on entry", findings=[],
                    cost=Cost(tokens=0, seconds=0.0, attempts=0), wall_seconds=0.0)
                await lift_ticket_files(
                    repo=repo, git=git, fs=LocalFilesystem(), effects=Effects(journal),
                    redact=log._redact, stem=o.stem, run_seq=o.run_seq, kind="harvest",
                    files=files)
                harvested = attempt
            except Exception as e:
                harvest_error = f"{type(e).__name__}: {e}"
                log.event("harvest_error", ticket=o.stem, run_seq=o.run_seq,
                          error=type(e).__name__, message=str(e),
                          traceback="".join(traceback.format_exception(e)))
        body = {"to": "abandoned", "run_seq": o.run_seq, "harvest": harvested}
        if harvest_error is not None:
            body["harvest_error"] = harvest_error
        journal.append("state_transition", body, ticket=o.stem)
        journal.append("signal", {
            "kind": "recovery_alert",
            "run_seq": o.run_seq,
            "disposition": "alert",
            "outcome": "abandoned",
            "reason": "orphan reaped during entry reconciliation",
        }, ticket=o.stem)
        if present:
            await git.worktree_remove(repo, path)
        else:
            await git.worktree_prune(repo)
        log.event("reconcile", ticket=o.stem, run_seq=o.run_seq, open_keys=list(o.open_keys),
                  worktree=str(path), removed=present)
        report(f"reconciled: {o.stem} run {o.run_seq} was left `running` by an interrupted "
               f"predecessor; journaled `abandoned`, worktree "
               f"{'removed' if present else 'already gone (registry pruned)'}")
    return found


def _workspace_base(events: Iterable[Event], orphan: Orphan) -> str:
    key = f"worktree/{orphan.stem}/{orphan.run_seq}"
    for event in reversed(tuple(events)):
        if event.type == "effect_completion" and event.ticket == orphan.stem and event.key == key:
            result = event.body["result"]
            if isinstance(result, dict) and isinstance(result.get("base"), str):
                return result["base"]
    raise ValueError(f"orphan {orphan.stem} run {orphan.run_seq} has no workspace base completion")
