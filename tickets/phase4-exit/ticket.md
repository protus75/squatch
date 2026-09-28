---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- reliability-run

## Context
- tickets/reliability-run/reliability-battery-report.json
- squatch/artifacts.py
- eval/reliability_battery.py
- tests/test_reliability_battery.py
- tests/test_seeded_phase4_02.py

## Plan contract
- section 20

## Goal
Close Phase 4 from its committed reliability evidence and author the fixed Phase
5 core.

## Why
The reliability run is the final execution-evidence producer; the exit admits
the bounded next-phase core only after that committed evidence is green.

## Scope in
Read only the committed `tickets/reliability-run/reliability-battery-report.json`
through `squatch.artifacts.ReliabilityBatteryReport` before authoring the Phase 5
core. Its exact, complete member order is
`classified_quota_exhaustion`, `all_candidates_cooling_recovery`, and
`unclassified_failure_preservation`; every member must be green. This is the sole
Phase 4 execution evidence. The prior watchdog obligations are proved by their
merged, transitive predecessors and are not report members or exit reads.

Author exactly confirmed `retro-drain-invoker`, `retro-box-activation`, and
`phase5-continue`, plus `tests/test_phase4_exit.py` and
`tests/test_seeded_phase5_core.py`. All three tickets cite section 20 alone and use
expected/stuck budgets within `drain.max_ticket_minutes`. `retro-drain-invoker`
depends on `phase4-exit`, is KNOWN-DEEP high/high, owns/fences new
`squatch/retro.py`, `specs/retro.md`, and `tests/test_retro.py`, plus existing
`squatch/drain.py`, `squatch/driver.py`, `squatch/__main__.py`,
`squatch/box.py`, `tests/test_drain.py`, `tests/test_driver.py`, and
`tests/test_box.py`; its Context is `squatch/driver.py`, `squatch/git.py`,
`squatch/box.py`, and `tests/test_seeded_phase4_02.py`, with the production
roots and large suites measured on-demand. Its fence also includes every
section-20-listed `main(["drain"])` merge/quiescence regression suite and names
the exact scripted-call, Box, journal, or main-history assertion migrated in
each. It writes
`tickets/retro/<seq>.md` directly in main through the ticket-plane Git/Effects
seam under the writer lock, never through the ordinary OUTBOX artifact lift;
it binds the default-off hook in `squatch/__main__.py::_drain` and pins section
20's exact N/M/S triggers, forced merge-since-report boundaries, and
single-message window-suppressed failure route. Its model dependency is the
existing `Driver` running an `LLMStage` named `retro` from `specs/retro.md`
through the session's shared provider/cooldown payload; the closed emitted
artifact and Markdown renderer live locally in `squatch/retro.py`.
The authored ticket enumerates every measured exception by path, including
`squatch/drain.py`, `squatch/__main__.py`, `tests/test_drain.py`,
`tests/test_driver.py`, `tests/test_box.py`, and each named regression suite;
it never substitutes a category phrase such as "all production roots."

`retro-box-activation`
depends on `retro-drain-invoker`, is KNOWN-DEEP high/high, owns/fences
the complete section-20 activation fence across retro, Box, Merge, Author,
triage, policy, stages/runner, daemon/drain/serve/status/CLI composition, their
named existing tests, and new `tests/test_retro_box.py`; this explicitly includes
existing `squatch/status.py`, while the not-yet-existing `tests/test_status.py`
is excluded from this activation fence. Its embedded Context is exactly
`squatch/box.py`, `tests/test_box.py`, `squatch/author.py`,
and `tests/test_seeded_phase4_02.py`; `tests/test_author.py`,
`squatch/status.py`, and the other
existing fence paths are individually named measured on-demand exceptions,
and predecessor-new retro paths are excluded at authoring. It pins the stable
per-proposal SHA-256 identity and Box origin,
the shared enqueue/semantic-triage `record_rereport` path with K=3,
journal-before-reopen
callback wiring, one-shot draft override, the `retro_ticket_authored` Author
bridge, and section 20's exact `retro_prompt_spec_change_merged` key, body,
provenance lookup, `specs/*.md` predicate, and successful merge emit point. The
ticket must preserve Merge's existing Box for Verification/base-failure filing
while forbidding use of that Box for retro provenance; retro provenance comes
only from the journal bridge.
`phase5-continue` depends on `retro-box-activation`, is medium/medium, owns only
`tickets` plus new `tests/test_seeded_phase5_01.py`, and embeds
`tests/test_seeded_phase4_05.py`; sibling-new core paths are never Context.
It states that merged `squatch/retro.py` and `tests/test_retro.py` are Context
for `scorecard-reporting` (or measured on-demand), with their authoring-time byte
sizes pinned as synthetic render fixtures that are never compared with later
live sizes, while only scorecard code, its test, and the next seeded test are
sibling-new. It also requires `phase5-continue-02` to embed the already-merged
`tests/test_seeded_phase4_05.py` continuation pattern and exclude new-in-admission
`tests/test_seeded_phase5_01.py` from Context. This regenerated revision
follows the successful `phase4-continue-05` merge and the completed section 20
integration-fence repair; that embedded predecessor Context now exists on main
and is preserved. Re-author all three ticket files in place from this revision;
the stem-owned outputs lifted by prior failed exit attempts are replaceable
outputs, not foreign collisions.

Carry this complete finite ordered admission registry:
```yaml
[[retro-drain-invoker, retro-box-activation, phase5-continue]]
```
The Phase 5 suffix is fixed: `phase5-continue` authors `scorecard-reporting`
plus `phase5-continue-02`; `phase5-continue-02` depends on
`scorecard-reporting` and authors `status-projection`, `baseline-binding-reader`,
plus `phase5-continue-03`; `phase5-continue-03` depends on both feature stems and
authors `retro-doctor-cli` plus `phase5-continue-04`; `phase5-continue-04`
depends on `retro-doctor-cli` and authors only `phase5-exit`, with no successor.

## Scope out
Do not implement or rerun the reliability battery, alter the committed report,
or rename, reorder, add, omit, combine, or split the Phase 5 core or suffix.

## Scope fence
- tickets
- tests/test_phase4_exit.py
- tests/test_seeded_phase5_core.py

## Acceptance criteria
- `tests/test_phase4_exit.py` proves the committed report parses as `ReliabilityBatteryReport`, has the closed three-member order, and every member is green before Phase 5 core authoring.
- `tests/test_seeded_phase5_core.py` pins the exact three core identities, edges, tiers, budgets, fences, Context partitions, predecessor-new and sibling-new exclusions, measured authoring-time sizes, bounded render, and fixed finite Phase 5 suffix.
- `tests/test_seeded_phase5_core.py` proves the invoker's CLI binding, direct reserved report lane, exact trigger/forced/failure semantics, the activation signal contract, and the scorecard's then-merged Context partition from section 20.
- `tests/test_seeded_phase5_core.py` proves the governed retro model/artifact path, all named CLI regression migrations, the complete activation fence, per-proposal identity, journaled reopen/draft route, and Author-to-Merge provenance bridge.

## Verification
```
uv run pytest tests/test_phase4_exit.py tests/test_seeded_phase5_core.py -q
uv run pytest -q
```

## Definition of rejected
Reject an uncommitted or non-green report, an obsolete report name or member, an
off-registry Phase 5 payload, sibling-new Context, or a successor after
`phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
