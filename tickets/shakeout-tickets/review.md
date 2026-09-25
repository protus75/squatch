---
verdict: snag
reviewed_sha: 6c77d0667b45596df92df5e0711023595c6e94a1
produced_by_spec_version: '1.0'
produced_at_sha: 6c77d0667b45596df92df5e0711023595c6e94a1
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The member module, the registry entry and the report run all match the ticket, and every check passed. One gap: the new unit test never checks that the drain's held line carries the finding's paved road; it only checks a separate direct lint call.

## Findings
- correctness_review at tests/test_tickets.py:460: Scope in requires the unit pin to show that 'the drain's scan holds a committed ticket that fails lint with the finding's paved road'. The acceptance criterion requires the ticket to be 'reported held: by the drain with the ticket_schema finding'. The test checks the drain output only for the finding's message text ('priority 'P9'', 'closed vocabulary'). Its `ticket_schema`/paved-road assertion, `any(f.code == CODE and f.paved_road for f in lint_error.findings)`, runs on a `refusal(bad, repo)` lint call that the test makes itself. `refusal()` already asserts that for every finding. So that line checks nothing about the drain. If the drain dropped or mangled the paved road in its held report (`held: {stem} {reason} -- {paved_road}`), this test would still pass. (paved road: Tie the lint finding to the drain output: take `f = lint_error.findings[0]`, then assert `f.code == CODE`, `f.message in line`, and `f.paved_road in line`, where `line` is the drain's `held: widget-parser ` line. Drop the disconnected `any(...)` assertion.)
