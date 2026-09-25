"""Reconcile-on-entry: reap the orphaned in-flight runs an interrupted
predecessor left (SQUATCH_PLAN.md section 11.2; section 18; section 19,
Phase 1).

The writer that just took the single-writer lock is the only writer, and no
daemon exists, so any run the journal still shows in flight is provably
dead: a stem whose last `state_transition` is `running` with no terminal, or
an `effect_intent` with no `effect_completion` after the stem's last
terminal. Phase 1 reaps bare -- an `abandoned` terminal appended through the
Journal seam, THEN the orphan worktree removed through git.py (the section
11.2 order: no worktree is wiped before its terminal is journaled). The
terminal frees the stem: the next run takes the next sequence and a fresh
keyspace, and its teardown-and-create clears the branch. Phase 2 folds the
harvest in ahead of the wipe; Phase 3 moves the whole step to daemon startup.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from squatch.artifacts import TERMINAL_RUN_STATES
from squatch.config import Config
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Event, Journal

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
        journal.append("state_transition", {"to": "abandoned", "run_seq": o.run_seq},
                       ticket=o.stem)
        path = repo / config.worktree_root / o.stem
        present = path.exists()
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
