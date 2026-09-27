---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- soak-run

## Context
- tests/test_seeded_phase3_11.py
- tests/test_serve.py

## Plan contract
- section 20

## Goal
Author the terminal Phase 3 exit seed.

## Why
The committed soak report now supplies evidence custody for the final Phase 3
exit read and the Phase 4 handoff.

## Scope in
Author only confirmed `phase3-exit`, plus `tests/test_seeded_phase3_23.py`.
`phase3-exit`, which depends on `soak-run`, is KNOWN-HARD high/high and owns
`tickets`, `tests/test_phase3_exit.py`, and `tests/test_seeded_phase4_core.py`.
It reads the committed `tickets/soak-run/daemon-soak-report.json` as evidence custody with `daemon-soak-runner` as machinery and `soak-run` as producer. Its exact
Context is the committed report, `squatch/artifacts.py`, `eval/daemon_soak.py`,
`tests/test_daemon_soak_runner.py`, and `tests/test_seeded_phase3_11.py`.
Its fence is owns followed by hooks, with no hooks. Both seeds cite section
20 alone, use 75m/150m budgets, and stay within `drain.max_ticket_minutes`.
The exit authors exactly the section 20 Phase 4 boundary registry's core batch
and pins that registry's finite ordered Phase 4 suffix; it does not invent,
rename, reorder, add, or omit a Phase 4 payload.

```yaml
ownership:
  phase3-exit:
    owns:
    - tickets
    - tests/test_phase3_exit.py
    - tests/test_seeded_phase4_core.py
    hooks: []
context:
  phase3-exit:
  - tickets/soak-run/daemon-soak-report.json
  - squatch/artifacts.py
  - eval/daemon_soak.py
  - tests/test_daemon_soak_runner.py
  - tests/test_seeded_phase3_11.py
```

`tests/test_seeded_phase3_23.py` pins the exact Context partition, no
on-demand exceptions, authoring-time Context sizes, predecessor-test closure,
new-path owners, sibling-new exclusions, and the max-effort
`specs/implement.md` render under `RENDER_BOUND_CHARS['max'] *
REQ_RENDER_HEADROOM`. Delimiter-bearing `squatch/specs.py` is never Context.
There is no successor after `phase3-exit`.

The finite ordered admission is:
```yaml
[[phase3-exit]]
```

## Scope out
Do not run the soak, implement the runner, author a successor, include a
sibling-new or delimiter-bearing Context path, or split the terminal batch.

## Scope fence
- tickets
- tests/test_seeded_phase3_23.py

## Acceptance criteria
- `tests/test_seeded_phase3_23.py` pins the exact phase3-exit identity, soak-run dependency, KNOWN-HARD high/high tier, 75m/150m budgets, cap 3, and owns-then-hooks fence.
- `tests/test_seeded_phase3_23.py` pins the exit Context partition including the `DaemonSoakReport` owner `squatch/artifacts.py`, no on-demand exceptions, authoring-time Context sizes, predecessor-test closure, new-path owners, and exclusion of sibling-new paths and `squatch/specs.py`.
- `tests/test_seeded_phase3_23.py` pins the singleton terminal admission, report evidence custody with daemon-soak-runner as machinery and soak-run as producer, max-effort render headroom, and no successor after phase3-exit.
- `tests/test_seeded_phase3_23.py` pins the section 20 Phase 4 core identities, ownership fences, dependency edges, and finite ordered suffix without inventing Phase 4 authority.

## Verification
```
uv run pytest tests/test_seeded_phase3_23.py -q
uv run pytest -q
```

## Definition of rejected
Reject a self-attested report, missing producer or machinery custody,
sibling-new Context, an embedded delimiter-bearing source, a missing render
proof, or a successor after the Phase 3 exit.

## Time budget
- expected: 75m
- stuck: 150m
