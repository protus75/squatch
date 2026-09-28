## Outcome
premise_failed

## Surprises / judgment calls
The current plan section 20 and ticket include squatch/watchdog.py and explicitly require attempt-level failover, so neither prior blocker applies. The plan was checked before implementation edits. Reused the inspected prior shared-payload implementation on files proven unchanged since its base, retained the Registry-to-Refusal conversion, then added classified cost-free parking and a single Resolved handoff from WatchdogLLM to CliClient. The shakeout bench now uses the restart-owned payload too, rather than constructing per-pipeline Timers.

Committed implementation: 933abfd6075bcad44368062cf503e4b02c1ebaad. Production drain and serve tests prove single- and multi-candidate quota attempts harvest and retire without infra, retry, or diagnosis draws; repeated polls/restarts hold without redispatch; timer_fired precedes resumed dispatch. The watchdog boundary test proves the selected identity and cost remain consistent across an initial-sample cooldown expiry. Construction spies prove one Registry and one live journal-backed Timers instance per production session. Config refusal regressions cover triage, drain, and serve. No configured live providers were changed.

## Dead ends
Full verification cannot exit 0 inside the scope fence: tests/test_seeded_phase4_01.py:208, test_successor_provider_ownership_and_authoring_contract, expects the continuation ownership hooks without squatch/watchdog.py, while tickets/phase4-continue-02/ticket.md:48 already includes that owner. Both paths are outside this ticket's edit fence. The base assertion and its exact parsing helpers were loaded from base a5be2634814eff11607a00ddf6ae1f483ee83df7 through the Git seam and executed against the same base's ticket blob in memory, with file reads restricted to those immutable blobs. That reproduction exits 1 at the same ownership assertion; implementation code is not involved in the failing comparison. No base checkout or unfenced file was edited.

Final verification on the committed implementation's exact file contents:
- uv run pytest tests/test_provider_cooldown_failover.py tests/test_providers.py tests/test_restart_timers.py tests/test_stages.py tests/test_serve.py tests/test_merge.py tests/test_mergequeue.py tests/test_daemon_composition.py -q: exit 0; 260 passed in 26.85 seconds.
- uv run pytest -q: exit 1; 1346 passed, one failed in 90.58 seconds. The sole failure is the base ownership mismatch above.

During test development, corrected fixture serialization that emitted forbidden null config values and retained an absolute derived worktree root. A multi-candidate expiry test also exposed that a synchronous timer observation should fire all elapsed deadlines before selecting a candidate; Timers.pending now does so, with idempotent firing against its background tasks.

Paved road: migrate tests/test_seeded_phase4_01.py's historical ownership expectation to include the already-authorized watchdog owner in a separately fenced change, then rerun full verification. Per the task's On-failure rule, the implementation is committed as far as it got; no tickets/ path was committed.

## Second problems filed
Pre-existing failure in tests/test_seeded_phase4_01.py::test_successor_provider_ownership_and_authoring_contract, reproduced from base a5be2634814eff11607a00ddf6ae1f483ee83df7 blobs as detailed above. Left untouched because its owning path is outside the fence.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving model identifier not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 12 minutes for inspection, implementation, focused and full verification, base-failure reproduction, and commit. Stopped on the out-of-fence verification blocker.
