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
- eval/daemon_soak.py
- tests/test_daemon_soak_runner.py

## Plan contract
- section 20

## Goal
Produce the daemon soak report through the ordinary lane.

## Why
The merged deterministic runner supplies the production evidence, and the
terminal Phase 3 exit consumes the committed ordinary-lane report.

## Scope in
Make no code changes. Invoke only the merged public deterministic runner and
the canonical ordinary-lane writer to produce
`tickets/soak-run/daemon-soak-report.json` in this worktree's OUTBOX. The
returned `DaemonSoakReport` is the writer input; the report is not self-attested.
This ticket has sole new-path ownership of that report.

## Scope out
Do not implement or alter the runner, run any scenario outside its merged
public contract, write the report directly, or author the Phase 3 exit.

## Scope fence
- tickets/soak-run/daemon-soak-report.json

## Acceptance criteria
- `tests/test_daemon_soak_runner.py` remains green while the ordinary lane consumes the merged public runner's returned `DaemonSoakReport` through the canonical writer.
- The only produced output is `tickets/soak-run/daemon-soak-report.json`, created through the ordinary lane rather than by a self-attesting direct write.

## Verification
```
uv run pytest tests/test_daemon_soak_runner.py -q
```

## Definition of rejected
Reject a code change, self-attested report, direct report write, or output
outside the report path.

## Time budget
- expected: 75m
- stuck: 150m
