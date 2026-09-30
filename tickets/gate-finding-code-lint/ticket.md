---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/gates.py
- squatch/artifacts.py
- tests/test_gates.py

## Goal
`_linted` in `squatch/gates.py` checks, for every gate `run_gates` runs, that each `Finding.code` inside that gate's `GateReport.findings` equals `gate.code`, not only the report's own top-level `code`. When a finding's code differs, `_linted` raises `GateLintError` naming the gate's code and the mismatched finding's code, exactly as it already does for a report whose own `code` differs.

## Why
`gate_lint` is the closed-protocol boundary every engine gate's report passes through before `run_gates` resolves severity from `gate.code` and files each finding into `GateRun.hard_failures` / `soft_failures` under that finding's own `code`. Today `_linted` only checks the report-level `code`, so a gate can emit a finding under another engine gate's code, or under a string that is not a code at all, and that mislabeled finding reaches `checks.json` and re-prompt findings misattributed. `RequisitionVerdict._finding_codes_are_closed` already enforces this per-finding closure for one model-facing artifact; this ticket puts the same check in `_linted`, the one place every engine gate report passes through. Host mechanical checks get their own adapter rule later (decision-000055) and are out of scope here.

## Scope in
- The per-finding code check inside `_linted` in `squatch/gates.py`, raising `GateLintError` on a mismatch with the same message shape the existing report-code check uses.
- A regression test in `tests/test_gates.py` giving `run_gates` a gate whose report code is correct but which carries one finding under another code, asserting `GateLintError`.
- A second test in `tests/test_gates.py` asserting that the same gate with all finding codes matching still runs to completion.

## Scope out
- `gate_lint`'s existing checks (unchanged; every engine gate already reaches `_linted` only after `gate_lint` admits it).
- Any individual gate's emitted finding codes (`ScopeFence`, `verification`, `run_record`, `diff_budget`, `bug_evidence`, `core_drift`, the rework `ticket_schema` gate, `RequisitionGate`) -- none need to change.
- Host mechanical check adapters and their code validation (a separate, later deliverable per decision-000055).

## Scope fence
- squatch/gates.py
- tests/test_gates.py

## Acceptance criteria
- `run_gates` raises `GateLintError` when a gate's report carries a finding whose `code` differs from `gate.code`, even though the report's own `code` matches, checked by `pytest tests/test_gates.py -k test_run_gates_rejects_finding_code_mismatch -q`.
- The raised `GateLintError`'s message names the gate's code and the mismatched finding's code, checked by the same `pytest tests/test_gates.py -k test_run_gates_rejects_finding_code_mismatch -q` (the test asserts both codes appear in the exception message).
- `run_gates` still runs a gate to completion when every finding's `code` matches `gate.code`, checked by `pytest tests/test_gates.py -k test_run_gates_allows_matching_finding_codes -q`.
- `pytest tests/test_gates.py -q` exits 0.
- `pytest -q` exits 0.

## Verification
```
pytest tests/test_gates.py -k test_run_gates_rejects_finding_code_mismatch -q
pytest tests/test_gates.py -k test_run_gates_allows_matching_finding_codes -q
pytest tests/test_gates.py -q
pytest -q
```

## Regression
```
pytest tests/test_gates.py -k test_run_gates_rejects_finding_code_mismatch -q
```
- carries: tests/test_gates.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing `gate_lint`, `RequisitionGate`'s verdict model, any individual gate's emitted finding codes, or a host mechanical check adapter -- that scope belongs to decision-000055's later deliverable, not this ticket.

## Time budget
- expected: 20m
- stuck: 45m
