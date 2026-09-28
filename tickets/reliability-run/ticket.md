---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- reliability-battery

## Context
- eval/reliability_battery.py
- squatch/artifacts.py
- tests/test_reliability_battery.py

## Plan contract
- section 20

## Goal
Produce the reliability-battery report through the ordinary lane.

## Why
The merged battery supplies the closed execution evidence that the terminal Phase
4 exit must read after ordinary-lane lift.

## Scope in
Make no code changes. Invoke only the merged public
`eval.reliability_battery.run(repo=<worktree>)` and the canonical ordinary-lane
writer to produce `tickets/reliability-run/reliability-battery-report.json` in
this worktree's OUTBOX. Write the returned report's `model_dump_json()` only;
leave that report uncommitted for the stage-terminal ordinary lift. This ticket
has sole new-path ownership of the report. `squatch/stages.py` is a measured
on-demand headroom exception: it supplies `KNOWN_ARTIFACTS` and ordinary lift,
but embedding its authoring-time bytes would exceed requisition headroom.

## Scope out
Do not implement or alter the reliability battery, run any behavior outside its
merged public contract, or author Phase 4 exit. A direct write means hand-authored
or edited report content, or any report content not returned by `run()`; reject it.

## Scope fence
- tickets/reliability-run/reliability-battery-report.json

## Acceptance criteria
- `tests/test_reliability_battery.py` remains green while the ordinary lane consumes the merged public battery's returned `ReliabilityBatteryReport` through the canonical writer.
- The only produced output is `tickets/reliability-run/reliability-battery-report.json`, containing `model_dump_json()` from `eval.reliability_battery.run(repo=<worktree>)`, uncommitted for ordinary lift and never hand-authored, edited, or otherwise non-`run()` content.

## Verification
```
uv run pytest tests/test_reliability_battery.py -q
```

## Definition of rejected
Reject a code change, reliability implementation or execution outside the merged
public battery, a self-attested or direct report write, report content not returned
by `run()`, a committed report, or output outside the report path.

## Time budget
- expected: 75m
- stuck: 150m
