---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- daemon-soak-runner

## Context
- tests/test_seeded_phase3_11.py
- tests/test_serve.py

## Plan contract
- section 20

## Goal
Author the no-code soak producer and the final shrinking Phase 3 continuation.

## Why
The runner supplies production evidence; the ordinary lane must now produce
the committed report before the terminal Phase 3 exit can consume it.

## Scope in
Author only confirmed `soak-run` and `phase3-continue-23`, plus
`tests/test_seeded_phase3_22.py`. `soak-run` depends on `daemon-soak-runner`,
is medium/medium, makes no code changes, and produces only
`tickets/soak-run/daemon-soak-report.json` through the ordinary lane.
`phase3-continue-23` depends on `soak-run`, is medium/medium, and authors
KNOWN-HARD high/high `phase3-exit` alone with no successor. Both cite section
20 alone, use 75m/150m budgets, stay within `drain.max_ticket_minutes`, and
the admission stays within cap 3 with fences derived as owns followed by hooks.

```yaml
ownership:
  soak-run:
    owns:
    - tickets/soak-run/daemon-soak-report.json
    hooks: []
  phase3-continue-23:
    owns:
    - tickets
    - tests/test_seeded_phase3_23.py
    hooks: []
context:
  soak-run:
  - eval/daemon_soak.py
  - tests/test_daemon_soak_runner.py
  phase3-continue-23:
  - tests/test_seeded_phase3_11.py
  - tests/test_serve.py
```

`phase3-continue-23` authors only `phase3-exit`: it depends on `soak-run`, is
KNOWN-HARD high/high, owns `tickets`, `tests/test_phase3_exit.py`, and
`tests/test_seeded_phase4_core.py`, and reads the committed report with
`daemon-soak-runner` as machinery and `soak-run` as producer. Pin every
emitted seed's exact Context partition, on-demand exceptions, authoring-time
Context sizes, predecessor-test closure, new-path owners, and each max-effort
`specs/implement.md` render under `RENDER_BOUND_CHARS['max'] *
REQ_RENDER_HEADROOM`. Exclude sibling-new paths and delimiter-bearing
`squatch/specs.py` from Context.

The finite ordered admissions are:
```yaml
[[soak-run], [phase3-exit]]
```
There is no successor after `phase3-exit`.

## Scope out
Do not run the soak, implement the runner, author phase3-exit now, combine the
admissions, include sibling-new or delimiter-bearing Context, or add a
successor after the exit.

## Scope fence
- tickets
- tests/test_seeded_phase3_22.py

## Acceptance criteria
- `tests/test_seeded_phase3_22.py` pins exact soak-run and continuation identities, dependencies, tiers, 75m/150m budgets, cap 3, and owns-then-hooks fences.
- The seeded test pins exact Context partitions, on-demand exceptions, authoring-time Context sizes, predecessor-test closure, new-path owners, and excludes sibling-new paths and `squatch/specs.py` from Context.
- `tests/test_seeded_phase3_22.py` pins the terminal `[[soak-run], [phase3-exit]]` suffix, downstream exit ownership and evidence custody, max-effort render headroom, and absence of a successor after Phase 3 exit.

## Verification
```
uv run pytest tests/test_seeded_phase3_22.py -q
uv run pytest -q
```

## Definition of rejected
Reject a combined admission, a self-attested report, missing producer or
machinery custody, sibling-new Context, an embedded on-demand fault reference,
a missing render proof, or a successor after Phase 3 exit.

## Time budget
- expected: 75m
- stuck: 150m
