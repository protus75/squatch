---
id: decision-000041
kind: decision
link: box-000041-26b2b333
reopen_after_days: 90
message: box-000041-26b2b333
---
No action. The message asks whether `limits.concurrency` should be optional until Phase 3. That question is now moot. Phases 3 through 6 have all closed (phase3-exit, phase6-exit merged). `thresh-runtime` merged the enforcement of provider concurrency, so the config key has a live consumer. The loader requires `concurrency: int = Field(ge=1)` (squatch/config.py:54). That matches section 15, which shows `limits: {concurrency: <int>, ...}` with no unset form (SQUATCH_PLAN.md:1301). The loader is correct as it stands. The section 19 Phase 1 wording (SQUATCH_PLAN.md:1467) and the bootstrap instruction 'Parse ONLY limits.est_cost_per_call_usd from the limits block ... the rest of limits is Phase 3's to parse and enforce' (SQUATCH_PLAN.md:357-359) only described how the work was staged during the bootstrap. They do not make the key optional in the finished engine. Relaxing it to `<int or unset>` would add a default-or-absent path to a key the merged threshold runtime reads, with no incident behind it, which the anti-bloat law rules out. No rendered ticket or decision covers the optionality of `limits.concurrency`. The open `config-gate-code-vocab` covers gate-code vocabulary and `host-contract-null-rule` covers explicit-null refusal, so a tombstone against either would be wrong. Reopen if a bootstrap regeneration from the plan fails because Phase 1's authored config omits `concurrency`. In that case, fix the section 19 / bootstrap wording in the plan so that it requires the key to be declared, and regenerate.

Evidence: squatch/config.py:53-54 (Limits.concurrency required, ge=1); SQUATCH_PLAN.md:1301 (section 15 `concurrency: <int>`); SQUATCH_PLAN.md:357-359 and :1467 (Phase 1 staging wording: parse only est_cost_per_call_usd); merged thresh-runtime (provider concurrency enforcement) and phase3-exit/phase6-exit show the Phase 3 consumer exists.
