---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- go-grade-machinery

## Context

## Plan contract
- section 20

## Goal
Execute the merged GO-grade harness once and deliver its closed report.

## Why
The exit reads committed execution evidence from this separate run lane.

## Scope in
Execute the merged harness once through its canonical producer/writer and
ordinary run lane. If the fixed cap is reached after at least one scorable
review, make `run_go_grade` journal and return that measured partial result as
valid NO-GO evidence instead of raising `Unscored`; no further model call is
made. An incomplete report must be refused by the operator-only `record_go`
path, so partial evidence can never become GO. Produce
`tickets/go-grade-run/review-baseline-report.json` in the worktree OUTBOX,
leaving it uncommitted for ordinary-lane validation and lift to the committed
report. Use the merged public entry point as implemented by `go-grade-machinery`;
never fabricate or hand-edit report fields.
The report embeds mechanically recorded GO-or-NO-GO verdict signal identity,
planted-defect count, spend, authored tickets, and dependency graph. Only the
operator may turn an earned result into GO; this machine run must not invoke
`--record-go`, and NO-GO is valid. Preserve the fixed USD 5.00 cap.
Embedded Context: none; measured on-demand: `eval/harness.py`,
`squatch/artifacts.py`, `tests/test_go_grade.py`. Read the merged public entry point, tests, and report schema
from the worktree only when needed; their post-machinery size is not embedded.

## Scope out
No artifact-schema change, production GO recording, host-loop execution, or successor authoring.

## Scope fence
- eval/harness.py
- tests/test_go_grade.py
- tickets/go-grade-run/review-baseline-report.json

## Acceptance criteria
- The merged harness executes once and its canonical writer returns `tickets/go-grade-run/review-baseline-report.json`, left uncommitted for ordinary lift.
- `tickets/go-grade-run/review-baseline-report.json` embeds the actual GO-or-NO-GO verdict signal identity and stays within USD 5.00; NO-GO is valid and only the operator records GO.
- `tests/test_go_grade.py` proves cap exhaustion after at least one scorable review produces a measured partial NO-GO report without another model call, and `record_go` refuses that incomplete report.

## Verification
```
uv run pytest tests/test_go_grade.py tests/test_eval_harness.py -q
```

## Definition of rejected
Reject changed contracts, unregistered or fabricated evidence, overflow, or successors.

## Time budget
- expected: 75m
- stuck: 150m
