---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- scorecard-reporting

## Context
- tests/test_seeded_phase4_05.py

## Plan contract
- section 20

## Goal
Author the next fixed Phase 5 admission and retain its finite suffix.

## Why
Scorecard reporting must merge before its two dependent Phase 5 features can be
admitted with a bounded continuation queue.

## Scope in
Author only confirmed `status-projection`, `baseline-binding-reader`, and
`phase5-continue-03`, plus `tests/test_seeded_phase5_02.py`. Use the already-
merged `tests/test_seeded_phase4_05.py` continuation pattern. The
already-merged `tests/test_seeded_phase5_01.py` is the Context pattern for the
authored `phase5-continue-03`; the new-in-this-admission
`tests/test_seeded_phase5_02.py` is excluded from every authored ticket's Context.
Sibling-new paths for this admission are `tests/test_status.py`,
`squatch/baseline.py`, `tests/test_baseline.py`, and
`tests/test_seeded_phase5_03.py`; sibling-new paths are never Context. Merged
`squatch/scorecard.py` and `tests/test_scorecard.py` are existing Context for
`status-projection`, with authoring-time sizes pinned as synthetic fixtures or
individually named measured on-demand exceptions. Every existing fence path of
these authored seeds is embedded Context or an individually named measured
on-demand exception. Only `squatch/scorecard.py`, `tests/test_scorecard.py`, and
`tests/test_seeded_phase5_02.py` were sibling-new in the first admission and
are excluded from that admission's Context.

All three tickets cite section 20 alone, start medium/medium, and use
expected/stuck budgets within `drain.max_ticket_minutes`. `status-projection`
depends directly on `scorecard-reporting` and `retro-box-activation`; it
owns/fences existing `squatch/status.py`, new `tests/test_status.py`, merged
`squatch/scorecard.py`, `tests/test_scorecard.py`, `squatch/box.py`,
`tests/test_box.py`, `squatch/retro.py`, `tests/test_retro.py`,
`squatch/__main__.py`, `tests/test_cli.py`, `tests/test_verbs.py`,
`tests/test_drain.py`, and `tests/test_drain_upgrade.py`. It preserves all
merged `Status` fields and CLI rendering while adding only `box_activity`,
`tombstone_digest`, and `scorecard`, with section 20's deterministic folds and
no journal, Box, ticket, or filesystem write.
`merged` is the sorted set of stems whose latest terminal transition is
`merged`; `in_flight` is sorted `(stem, run_seq)` for latest unmatched
`running` transitions; and `blocked` is sorted `(stem, unmet_dependencies)`
for confirmed unmerged tickets with an unmerged declared dependency.
`spend_usd` sums numeric `effect_completion.body.cost.usd`; `box_activity`
counts Box records by current status; `tombstone_digest` is sorted `(box_id,
signature, reports, reopened)` for tombstone-resolved records; and `scorecard`
is the current-window `project_scorecard` result. Production `_status` passes
its injected clock, resolves actual HEAD through `Git.rev_parse`, loads the
real `specs/retro.md` version, and constructs `Window(events,
clock()).projection(sha=head_sha, spec_version=retro_spec.version)`; the CLI may
become async internally but preserves its exit/output contract. Malformed
optional metric bodies are excluded while journal-envelope corruption remains
fail-closed.

`baseline-binding-reader` depends directly on `retro-box-activation`; it
owns/fences new `squatch/baseline.py` and `tests/test_baseline.py`, plus existing
`squatch/journal.py`, `squatch/config.py`, `squatch/policy.py`,
`tests/test_policy.py`, `squatch/author.py`, `tests/test_author.py`, and
`tests/test_retro_box.py`. It exposes immutable
`BaselineResolution(state, binds)` with closed `ABSENT | NO_GO | GO | REVOKED`
precedence; only identity-matching `GO` binds. `resolve_baseline(config, events,
*, specs_dir)` compares the current registry and review/author spec-major
versions explicitly, never through globals. Torn journal tails, malformed
identity/spec fields, missing or empty routing, unresolved placeholders, unknown
tiers, and unreadable specs resolve to the supervised side without raising.
`squatch/author.py` is the sole production caller: it passes current config,
`Journal.read()` events, and `<repo>/specs`, then passes `resolution.binds` to
`policy.starting_state`. The implementation migrates and removes existing
`policy.go_binds`; it never leaves a second binding reader in `policy.py`.
No review-baseline record resolves `ABSENT`; a latest verdict other than `GO`
resolves `NO_GO`; and a `GO` resolves `GO` only when every recorded review and
author tier identity matches the current `Registry(config)` and recorded
`spec_major` values match the review and author specs. Otherwise it resolves
`REVOKED`; only `GO` sets `binds=true`. A torn tail or malformed identity/spec
input is `REVOKED` for a selected `GO`, otherwise the applicable `ABSENT` or
`NO_GO`.

`phase5-continue-03` depends on both feature stems, owns only `tickets` and new
`tests/test_seeded_phase5_03.py`, and embeds merged
`tests/test_seeded_phase5_01.py`, never this admission's new seeded test.
`tests/test_seeded_phase5_02.py` pins this Context
partition, the synthetic authoring-size fixtures, and proves every emitted
seed's max-effort `specs/implement.md` render remains within
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

Carry this complete finite ordered admission registry:
```yaml
- [status-projection, baseline-binding-reader, phase5-continue-03]
- [retro-doctor-cli, phase5-continue-04]
- [phase5-exit]
```
`phase5-continue-04` depends on `retro-doctor-cli`, owns only `tickets` and new
`tests/test_seeded_phase5_04.py`, and embeds merged
`tests/test_seeded_phase5_02.py`, never the seeded test created in its own
admission. `retro-doctor-cli` owns/fences new `squatch/doctor.py` and
`tests/test_doctor.py`, plus `squatch/retro.py`, `squatch/__main__.py`,
`tests/test_retro.py`, `tests/test_cli.py`, and `tests/test_verbs.py`. Every
existing path is embedded Context or an individually named measured on-demand
exception with its authoring-time byte size pinned in
`tests/test_seeded_phase5_03.py`. `phase5-exit` is KNOWN-HARD high/high, depends transitively on
every Phase 5 stem, owns/fences `tickets`, new `tests/test_phase5_exit.py`, and
new `tests/test_seeded_phase6_core.py`, and has no successor.

## Scope out
Do not implement a Phase 5 feature, use sibling-new Context, use
`tests/test_seeded_phase5_02.py` as same-admission Context, leave a second
baseline reader in `policy.py`, replace existing status fields/rendering, reorder the
registry, or add a successor after `phase5-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase5_02.py

## Acceptance criteria
- `tests/test_seeded_phase5_02.py` pins the exact second-row identities, direct edges, tiers, budgets, ownership fences, section-20-only contracts, and three-seed admission cap.
- `tests/test_seeded_phase5_02.py` pins the Phase 4 continuation fixture, new-in-admission and sibling-new Context exclusions, every existing-fence Context/on-demand disposition, synthetic sizes, and max-effort render headroom.
- `tests/test_seeded_phase5_02.py` proves preservation of existing status fields/rendering, the three additive fields and folds, the explicit clock/HEAD/spec-version retro projection source, and the complete CLI/preservation fence.
- `tests/test_seeded_phase5_02.py` proves the closed baseline precedence, supervised fallback, identity inputs, migration/removal of `policy.go_binds`, and complete policy/Author caller and test fence.
- `tests/test_seeded_phase5_02.py` pins `phase5-continue-03` to merged `tests/test_seeded_phase5_01.py`, excludes its own new seeded test from Context, and pins `phase5-continue-04` to merged `tests/test_seeded_phase5_02.py`.
- `tests/test_seeded_phase5_02.py` carries every remaining row, dependency, owner, terminal, and no-successor boundary verbatim.

## Verification
```
uv run pytest tests/test_seeded_phase5_02.py -q
uv run pytest -q
```

## Definition of rejected
Reject an off-registry feature, sibling-new Context, the wrong continuation
fixture, more than three seeds, or a successor after `phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
