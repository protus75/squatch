---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- go-grade-run

## Context
- squatch/artifacts.py
- tests/test_gates.py

## Plan contract
- section 20

## Goal
Build the closed host-loop evidence machinery for the Phase 6 exit.

## Why
The terminal receipt needs registered, reproducible host-loop evidence rather
than fabricated exit inputs.

## Scope in
Register closed ordinary-lane writers for `host-loop-report.json` and
`exit-receipt.json` in `squatch/artifacts.py` and `squatch/stages.py`. Build
`eval/host_loop.py` and `tests/test_host_loop.py` as the supervised `serve`
host-loop harness. It launches `serve` against `hosts/fixture/`, drives machine-actor
`confirm` requests through the control inbox, and records per-member
`(member, driven scenario, observable, producing run)` evidence for at least
three machine-ticket merges, the report-to-regression bug loop, and escape
attribution. The machinery never produces terminal artifacts during its
own build.
Add the fixture `triage` route in `hosts/fixture/config.yaml` and its
deterministic triage response in `hosts/fixture/bin/codex`, so real inbox
reports become regression-bearing Author tickets and later escape attribution
through the production Serve/triage path rather than fabricated entries.

Embedded Context: `squatch/artifacts.py`, `tests/test_gates.py`. Measured
on-demand worktree reads: `squatch/stages.py`, `tests/test_stages.py`,
`hosts/fixture/`. Read them before editing; the fixture directory is never
embedded Context. New `eval/host_loop.py` and `tests/test_host_loop.py` are
not Context.

## Scope out
Do not run the terminal exit, hand-author host-loop evidence, add a successor,
or produce terminal artifacts during this build.

## Scope fence
- squatch/artifacts.py
- squatch/stages.py
- eval/host_loop.py
- tests/test_host_loop.py
- tests/test_gates.py
- tests/test_stages.py
- hosts/fixture/config.yaml
- hosts/fixture/bin/codex

## Acceptance criteria
- `tests/test_host_loop.py` proves both closed artifact schemas and ordinary-lane writer registration, including unknown-field refusal.
- `tests/test_host_loop.py` proves the supervised fixture-host harness drives control-inbox confirms and records member, scenario, observable, and producing-run evidence for three machine-ticket merges, the report-to-regression bug loop, and escape attribution.
- `tests/test_host_loop.py` proves the scripted fixture `triage` route drives those report-to-ticket and escape loops through the real inbox/Serve path.
- `tests/test_host_loop.py`, `tests/test_gates.py`, and `tests/test_stages.py` prove construction produces no terminal host-loop or exit receipt artifact.

## Verification
```
uv run pytest tests/test_host_loop.py tests/test_gates.py tests/test_stages.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, unregistered or fabricated evidence, terminal output
during construction, overflow, or successors.

## Time budget
- expected: 75m
- stuck: 150m
