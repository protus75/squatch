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
- retro-box-activation

## Context
- squatch/status.py
- squatch/scorecard.py
- tests/test_scorecard.py
- squatch/box.py
- tests/test_box.py

## Plan contract
- section 20

## Goal
Make status the deterministic, read-only Phase 5 projection.

## Why
Operators need one status value that includes the merged retro, Box, and
scorecard evidence without changing the existing status surface.

## Scope in
Preserve every merged `Status` field and existing CLI/file/slash rendering:
`unparsed`, `pending`, `in_flight`, `ready`, `blocked`, `stopped`, `merged`,
`intake`, `spend_usd`, `calls`, `box`, and `reject_queue`. Add only
`box_activity`, `tombstone_digest`, and `scorecard`. Fold `merged` as the
sorted stems whose latest terminal transition is `merged`; `in_flight` as
sorted `(stem, run_seq)` for latest unmatched `running`; and `blocked` as
sorted `(stem, unmet_dependencies)` for confirmed unmerged tickets with an
unmerged declared dependency. Sum numeric `effect_completion.body.cost.usd`;
count Box records by current status; and make the tombstone digest sorted
`(box_id, signature, reports, reopened)` for tombstone-resolved records.

Production `_status` passes its injected clock, resolves actual HEAD through
`Git.rev_parse`, loads the real `specs/retro.md` version, and constructs
`Window(events, clock()).projection(sha=head_sha, spec_version=retro_spec.version)`
before `project_scorecard`. It may become async internally while preserving
the public CLI exit/output contract. Exclude malformed optional metric bodies;
leave journal-envelope corruption fail-closed. Projection and every rendering
consume the same deterministic value and perform no journal, Box, ticket, or
filesystem write.

The fenced measured on-demand inspection exceptions are `squatch/retro.py`
(17745 bytes), `tests/test_retro.py` (20072 bytes), `squatch/__main__.py`
(24624 bytes), `tests/test_cli.py` (19367 bytes), `tests/test_verbs.py` (9901
bytes), `tests/test_drain.py` (42002 bytes), and
`tests/test_drain_upgrade.py` (14377 bytes). These are synthetic
authoring-time sizes, never live-size assertions. New `tests/test_status.py`
is this ticket's only new test path.

Historical preservation repair: `tests/test_seeded_phase2.py` pins its closed
Context-refused set from the Phase 2 authoring commit instead of rescanning
later live files. Later legitimate `tests/test_cli.py` growth must not
retroactively invalidate the already-admitted `spine-harvest` Context.

## Scope out
Do not remove or replace an existing status field or rendering, invent
provenance, write through a projection, or make malformed journal envelopes
best-effort.

## Scope fence
- squatch/status.py
- tests/test_status.py
- squatch/scorecard.py
- tests/test_scorecard.py
- squatch/box.py
- tests/test_box.py
- squatch/retro.py
- tests/test_retro.py
- squatch/__main__.py
- tests/test_cli.py
- tests/test_verbs.py
- tests/test_drain.py
- tests/test_drain_upgrade.py
- tests/test_seeded_phase2.py

## Acceptance criteria
- `tests/test_status.py` proves every preserved field/rendering plus exactly the three additive fields and all deterministic folds.
- `tests/test_status.py` proves the injected-clock, HEAD, and retro-spec-version scorecard source and optional-metric exclusion.
- `tests/test_cli.py` and `tests/test_verbs.py` preserve the CLI output and exit contract.
- `tests/test_drain.py` and `tests/test_drain_upgrade.py` preserve callers without projection writes.
- `tests/test_seeded_phase2.py` pins its Context-refused set to the Phase 2 authoring-time snapshot instead of rescanning later live files.

## Verification
```
uv run pytest tests/test_status.py tests/test_scorecard.py tests/test_box.py tests/test_retro.py tests/test_cli.py tests/test_verbs.py tests/test_drain.py tests/test_drain_upgrade.py -q
uv run pytest -q
```

## Definition of rejected
Reject a removed status surface, a different rendering value, fabricated
provenance, a write, or a malformed optional metric treated as valid.

## Time budget
- expected: 75m
- stuck: 150m
