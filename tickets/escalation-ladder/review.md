---
verdict: snag
reviewed_sha: e5c93757fbd310cb9cef651856b99fe80d3ed2a1
produced_by_spec_version: '1.0'
produced_at_sha: e5c93757fbd310cb9cef651856b99fe80d3ed2a1
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The ladder module, routing arms, runner wiring, rung-carrying cap draw and tests meet the acceptance criteria and stay inside the fence. However, drain.py changes the Reject-queue auto-keep, which the ticket's Scope out forbids.

## Findings
- correctness_review at squatch/drain.py:294: `_resolve_rejects` now skips the machine auto-keep for any reject whose reason contains the text "capability ladder exhausted". This breaks two explicit rules in the ticket: Scope out says "No change to ... the auto-keep", and Scope in says "nothing else in eligibility, park, or re-offer changes". The check also relies on a substring of a free-text reason string instead of a structured field, so rewording the message in reject.py would silently change park behavior. `test_exhausted_ladder_stays_reported_in_the_reject_queue` (`len(fake.calls) == 4`) locks in the changed behavior. The acceptance criterion "a stem that exhausts the ladder is reported under `reject queue:`" does not need this edit. With the auto-keep unchanged, the stem is re-offered at the top rung until its retry cap runs out and then stays reported in the Reject queue. (paved road: Revert the `_resolve_rejects` change so auto-keep behaves exactly as landed. Rewrite the exhausted-ladder drain test to assert that the stem ends up reported under `reject queue:` with the exhausted-ladder reason, without pinning the call count to 4. If exhausted stems really must not be auto-kept, that is a plan/ticket change: file it through the Suggestion Box instead of folding it into this diff.)
