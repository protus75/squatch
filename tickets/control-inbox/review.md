---
verdict: snag
reviewed_sha: c4db3cac4fd8841404c72be4ba6dfedc4b62ee0b
produced_by_spec_version: '1.0'
produced_at_sha: c4db3cac4fd8841404c72be4ba6dfedc4b62ee0b
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Publication, identity checks, invalid/conflict handling and the daemon hook are sound, and all checks are green. One problem remains: a crash between the journaled accept and the mutation lets an old-lifecycle request run against the next lifecycle after a restart, which breaks the stale-lifecycle criterion.

## Findings
- correctness_review at squatch/control.py:118: In `consume`, a request that already has a journaled decision is replayed without checking it against the current inbox. The `accepted` outcome decided under lifecycle A is reused and `mutate(request)` runs. If the daemon crashes after the decision is appended but before the mutation or unlink, the restarted inbox gets a fresh lifecycle B from `uuid4`. The leftover file for lifecycle A is then replayed, so its pause, kill or resume is applied to lifecycle B. A replayed `release` also calls `self._holds.discard` on lifecycle B's hold set. The ticket requires that stale lifecycle requests and releases never affect later identities. The replay test only replays inside the same `ControlInbox` instance, so it never covers the restart crash point. (paved road: When replaying a decision that is already journaled, only run the governed mutation if `decision.request.lifecycle == self.lifecycle`. Otherwise unlink the file and return the decision without mutating; for a release, also skip the hold discard. Add a `tests/test_control.py` case: publish and accept under lifecycle A, crash inside `mutate`, build a new `ControlInbox` with lifecycle B on the same journal and state dir, call `consume`, and assert that `mutate` is not called and no hold is discarded.)
