---
verdict: snag
reviewed_sha: 6a482c8ec63f132390cc1c3e901ddebac43d4356
produced_by_spec_version: '1.0'
produced_at_sha: 6a482c8ec63f132390cc1c3e901ddebac43d4356
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The verbs, the cap fold bound, the premise_bounce draw and the drain eligibility match the ticket, and the checks are green. Three fixable defects remain: `reject` crashes after a partial journal write on a ticket with broken frontmatter, and two rules in Scope in have no test even though the ticket says every rule gets one.

## Findings
- correctness_review at squatch/runner.py:222: `Runner.reject` catches the `ValueError` from `parse_frontmatter` for a committed ticket with missing or unterminated `---` fences. It then calls `stamp(text, state="rejected")`, which raises `ValueError("stamp needs frontmatter between \`---\` fences")` on the same input, and nothing catches that. By this point the `reject` signal and the `to: rejected` transition are already journaled. The verb therefore crashes with a traceback instead of exiting 0. It commits no stamp and never runs the dead-dependency handling, so dependents are never reported and no `failure_report` is enqueued. The ticket says 'a kill never asks the ticket to be valid', and the parse try/except shows the code meant to handle this case. (paved road: Handle the unstampable case before any journal write. One option is to check that stamping is possible up front and treat an unstampable ticket like the dirless ghost: journal-only, then continue to the dead-dependency handling. Add a `tests/test_verbs.py` case for rejecting a committed ticket with broken frontmatter that asserts exit 0, the reject signal, the transition, and the dependent reports.)
- correctness_review at tests/test_verbs.py: Scope in has the rule 'a stem that is confirmed, never run, and not awaiting anything is refused as nothing to confirm' and says 'Tests for every rule above'. `runner.py` implements this refusal at lines 186-190, but no test covers it: no test confirms a committed, confirmed, never-run stem and asserts exit 2 with no journal write. (paved road: Add a `tests/test_verbs.py` test: commit a confirmed ticket with an intake signal and no transitions, run `squatch confirm <stem>`, and assert exit 2, the refusal message, and an unchanged journal.)
- correctness_review at tests/test_drain.py: Scope in requires 'the spent-retry road line names `squatch confirm <stem>` as the re-arm', and `drain.py` line 377 changes that line, but no test asserts it. A grep of `tests/` finds no assertion on the spent-retry parked line containing `squatch confirm`. (paved road: Add a drain test: a stem parked `gate_failed` with its retry cap spent (for example config `caps: {retry: 0}` or enough journaled retry draws). Assert its parked line contains `retry cap spent` and `squatch confirm <stem>`.)
