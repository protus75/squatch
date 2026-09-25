---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase2-exit

## Context
- squatch/__main__.py

## Plan contract
- section 20

## Goal
The dormant Phase 3 scheduler core dispatches one ticket at a time and accepts watcher-driven priority snapshots without becoming reachable from the production composition.

## Why
Section 20 makes construction deliberately sub-production: the scheduler and watcher must be directly testable before a later activation ticket changes callers. The dormancy proof is behavioral evidence about reachability, not a direct-import grep: production is the transitive `squatch.*` import closure rooted at `squatch/__main__.py`, so an import through `drain.py`, `runner.py`, or another reachable module must fail the proof too.

## Scope in
`squatch/scheduler.py` owns an asyncio single-flight scheduler: one injected async dispatch callback may be in flight, a new ordered offer snapshot may replace only the waiting order, and the in-flight stem is neither duplicated nor cancelled by reprioritization. `squatch/watcher.py` owns the dormant watcher adapter that converts each observed ticket-plane change into a fresh priority snapshot for that scheduler; burst updates converge on the latest snapshot without creating a second dispatcher. `tests/test_scheduler.py` exercises both modules directly and implements the dormancy scan as the transitive local `squatch.*` import closure rooted at `squatch/__main__.py`, parsed with `ast` and recognizing `import squatch.x`, `from squatch import x`, and `from squatch.x import y`; the scan fails when `squatch.scheduler` or `squatch.watcher` is reachable, including through an intermediate local module.

## Scope out
No production import, CLI verb, daemon loop, merge queue, control surface, journal event, config key, or scheduler activation. No polling policy or filesystem backend beyond the injected watcher input. The later `scheduler-activation` ticket owns production composition and migration of the negative dormancy assertion.

## Scope fence
- squatch/scheduler.py
- squatch/watcher.py
- tests/test_scheduler.py

## Acceptance criteria
- In `tests/test_scheduler.py`, a blocked first dispatch plus multiple replacement snapshots never overlaps dispatch calls, never dispatches the in-flight stem twice, and dispatches the highest-ranked remaining stem from the latest snapshot next.
- In `tests/test_scheduler.py`, watcher notifications drive scheduler reprioritization and a burst that arrives while one dispatch is active converges on the final observed snapshot without spawning another dispatch loop.
- In `tests/test_scheduler.py`, an AST walk of the transitive local `squatch.*` import closure rooted at `squatch/__main__.py` recognizes both import forms, rejects a synthetic indirect path to each of `squatch.scheduler` and `squatch.watcher`, and confirms neither module is reachable from the real production root.
- `uv run pytest tests/test_scheduler.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_scheduler.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if single-flight scheduling or watcher reprioritization requires a production caller before the activation ticket, if the transitive AST closure cannot model the package's real import forms without changing an existing file, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
