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
new-in-this-admission `tests/test_seeded_phase5_01.py` is excluded from Context.
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
owns/fences existing `squatch/status.py`, new `tests/test_status.py`, and the
merged `squatch/scorecard.py`, `tests/test_scorecard.py`, `squatch/box.py`, and
`tests/test_box.py`. It returns one immutable read-only projection with exactly
`merged`, `in_flight`, `blocked`, `spend_usd`, `box_activity`,
`tombstone_digest`, and `scorecard`, with section 20's deterministic folds for
each field and no journal, Box, ticket, or filesystem write.

`baseline-binding-reader` depends directly on `retro-box-activation`; it
owns/fences new `squatch/baseline.py` and `tests/test_baseline.py`, plus existing
`squatch/journal.py`, `squatch/config.py`, `squatch/author.py`,
`tests/test_author.py`, and `tests/test_retro_box.py`. It exposes immutable
`BaselineResolution(state, binds)` with closed `ABSENT | NO_GO | GO | REVOKED`
precedence; only identity-matching `GO` binds. `resolve_baseline(config, events,
*, specs_dir)` compares the current registry and review/author spec-major
versions explicitly, never through globals. Torn journal tails, malformed
identity/spec fields, missing or empty routing, unresolved placeholders, unknown
tiers, and unreadable specs resolve to the supervised side without raising.
`squatch/author.py` is the sole production caller: it passes current config,
`Journal.read()` events, and `<repo>/specs`, then passes `resolution.binds` to
`policy.starting_state`; `squatch/policy.py` is not the binding reader or its
caller.

`phase5-continue-03` depends on both feature stems, owns only `tickets` and new
`tests/test_seeded_phase5_03.py`, and embeds the immediately preceding merged
seeded-test pattern. `tests/test_seeded_phase5_02.py` pins this Context
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
`tests/test_seeded_phase5_04.py`, and embeds its immediately preceding merged
seeded-test pattern. `retro-doctor-cli` owns/fences new `squatch/doctor.py` and
`tests/test_doctor.py`, plus `squatch/retro.py`, `squatch/__main__.py`, and their
focused tests. `phase5-exit` is KNOWN-HARD high/high, depends transitively on
every Phase 5 stem, owns/fences `tickets`, new `tests/test_phase5_exit.py`, and
new `tests/test_seeded_phase6_core.py`, and has no successor.

## Scope out
Do not implement a Phase 5 feature, use sibling-new Context, use
`tests/test_seeded_phase5_01.py` as the continuation fixture, reorder the
registry, or add a successor after `phase5-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase5_02.py

## Acceptance criteria
- `tests/test_seeded_phase5_02.py` pins the exact second-row identities, direct edges, tiers, budgets, ownership fences, section-20-only contracts, and three-seed admission cap.
- `tests/test_seeded_phase5_02.py` pins the Phase 4 continuation fixture, new-in-admission and sibling-new Context exclusions, every existing-fence Context/on-demand disposition, synthetic sizes, and max-effort render headroom.
- `tests/test_seeded_phase5_02.py` proves the exact immutable status fields and folds, plus the closed baseline precedence, supervised fallback, identity inputs, and concrete Author caller/test fence.
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
