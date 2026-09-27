---
verdict: snag
reviewed_sha: f865ecac71710244cb7d567b8951896ea2d0e380
produced_by_spec_version: '1.0'
produced_at_sha: f865ecac71710244cb7d567b8951896ea2d0e380
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The three tickets and the seeded test cover the registry shape and all edits stay inside the fence. But `phase4-continue-02` contradicts itself, `watchdog-activation` is authored high/high without plan authority, and the test pins a wrong authoring-time Context size for `squatch/providers.py`.

## Findings
- correctness_review at tickets/phase4-continue-02/ticket.md:80: Scope out says "do not author the provider payload now", but Scope in (line 29) says "Author only confirmed `provider-cooldown-failover` and `phase4-continue-03`". Authoring that provider ticket is the continuation's whole job, so its implementer cannot satisfy both sections. That makes the continuation unsatisfiable, and the parent ticket's Definition of rejected covers this case. (paved road: Change Scope out to forbid implementing provider cooldown/failover behavior, reliability machinery, and any payload beyond `provider-cooldown-failover` plus `phase4-continue-03`. Remove the "do not author the provider payload now" clause.)
- correctness_review at tickets/watchdog-activation/ticket.md:6: `watchdog-activation` is authored `agent_tier: high, agent_effort: high`, and the test pins that at tests/test_seeded_phase4_01.py:96. The parent ticket requires every authored ticket to start at the registry tier. Plan section 20 (line 1559) names only `provider-cooldown-failover` as KNOWN-DEEP and `phase4-exit` as KNOWN-HARD; it never raises `watchdog-activation`. Section 13 defaults authored tickets to medium, and a known-hard raise must record its citing evidence in the seed. This ticket records none. (paved road: Author `watchdog-activation` at medium/medium and update the test's tier assertion to match. If it really needs a raised starting tier, name it in plan section 20 first, then record that citation in the ticket.)
- correctness_review at tests/test_seeded_phase4_01.py:42: `EXISTING_AT_AUTHORING` gives `squatch/providers.py` a size of 32667 characters, but the file at the implemented head (f865eca) is 18687 bytes. The pinned authoring-time Context size is not the real one. The other six sizes match. The headroom test renders placeholder text of these sizes, so it passes against a size that never existed, and the next continuation inherits the wrong number. (paved road: Pin the real authoring-time size (18687), or better, assert each pinned size against the file's actual length at test time so drift fails loudly.)
- correctness_review at tests/test_seeded_phase4_01.py:118: Uncertain: delimiter-bearing Context exclusion is checked only against a hardcoded set (`squatch/specs.py`, `specs/implement.md`). The acceptance criterion asks the test to prove exclusion of delimiter-bearing prompt sources. Other tracked files contain the `squatch:data` / `squatch:end` delimiters (for example tests/test_specs.py, tests/test_stages.py), and a hardcoded list would miss them if a later edit added one to Context. (paved road: Read each Context path's content and assert that it contains neither the `<<<squatch:data` nor the `<<<squatch:end` delimiter. Keep the explicit `squatch/specs.py` assertion.)
