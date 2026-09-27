---
verdict: snag
reviewed_sha: 69c97ab7d8ce7b22de351b17b06a2aaa764dea93
produced_by_spec_version: '1.0'
produced_at_sha: 69c97ab7d8ce7b22de351b17b06a2aaa764dea93
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The wiring, rehydration and tests are sound, but the CLI decides whether the lock holder is a live control consumer using an identity that is not unique per process. It can therefore report a successful publish to a holder that will never consume the request.

## Findings
- correctness_review at squatch/__main__.py:190: The live-engine branch of `_control` passes `held.holder.instance_id` to `_published_lifecycle`, which returns the most recent `control_lifecycle` signal for that holder string. The drain gets its holder from `_locked`'s `instance_id = await git.describe(ENGINE_ROOT)`. That is the engine version string, and every lock holder shares it: `run`, `confirm`, `reject`, `triage` and each successive drain. Failure case: a drain (instance vX) publishes lifecycle L1 and exits. Then `squatch run foo` (also vX) holds the lock. `squatch pause` finds L1, publishes the request, prints `published pause: hold id ...` and exits 0. But no control consumer is running. The next drain mints a new lifecycle because no hold or accepted work is active, so the request is decided stale. The operator is told the pause was published, yet it never takes effect. The refusal 'the lock holder is not a live drain control consumer' is meant to prevent exactly this, but the check fails open. It also defeats the ticket's live-lock publication and stale-identity guarantee (acceptance criterion 1). (paved road: Bind the published lifecycle to the specific live lock acquisition, not the engine version. For example, have the drain's `control_lifecycle` signal record the lock holder's `pid` and `started_at` (from the Holder the lockfile writes). Have `_published_lifecycle` match on those fields from `held.holder`, and refuse when nothing matches. Add a `tests/test_control_cli.py` case where a non-drain holder with the same `instance_id` as an earlier drain is refused.)
