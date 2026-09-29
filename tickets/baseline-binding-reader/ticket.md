---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- retro-box-activation

## Context
- squatch/config.py
- squatch/policy.py

## Plan contract
- section 20

## Goal
Move baseline binding resolution into its closed, explicit reader.

## Why
Authoring must decide confirmation from current routing and specs through one
supervised, testable identity boundary.

## Scope in
Add immutable `BaselineResolution(state, binds)` in `squatch/baseline.py`, with
the closed states `ABSENT | NO_GO | GO | REVOKED`. `resolve_baseline(config,
events, *, specs_dir)` selects the latest complete `signal` of kind
`review_baseline`: no record is `ABSENT`; a latest non-`GO` verdict is `NO_GO`;
and a `GO` is `GO` only if every recorded review and author tier identity
equals current `Registry(config)` resolution and recorded `spec_major` equals
the major versions from `specs_dir/review.md` and `specs_dir/author.md`.
Otherwise it is `REVOKED`; only `GO` sets `binds=true`.

Torn journal tails, malformed identity/spec fields, missing or empty routing,
unresolved placeholders, unknown tiers, and unreadable specs never escape:
they yield `REVOKED` for a selected GO and otherwise the applicable `ABSENT`
or `NO_GO`. Migrate and remove `policy.go_binds`; `policy.starting_state`
remains sole starting-state policy. `squatch/author.py` is the sole production
caller: it passes current config, `Journal.read()` events, and `<repo>/specs`,
then passes `resolution.binds` to `policy.starting_state`.

The fenced measured on-demand inspection exceptions are `squatch/journal.py`
(8792 bytes), `squatch/author.py` (15087 bytes), `tests/test_policy.py` (4836
bytes), `tests/test_author.py` (19061 bytes), and `tests/test_retro_box.py`
(29276 bytes). These are synthetic authoring-time sizes, never live-size
assertions. New `tests/test_baseline.py` owns the reader behavior.

## Scope out
Do not leave a second binding reader or production caller in `policy.py`, use a
global specs lookup, raise on supervised input, or bind a nonmatching GO.

## Scope fence
- squatch/baseline.py
- tests/test_baseline.py
- squatch/journal.py
- squatch/config.py
- squatch/policy.py
- tests/test_policy.py
- squatch/author.py
- tests/test_author.py
- tests/test_retro_box.py

## Acceptance criteria
- `tests/test_baseline.py` proves the closed precedence, only-GO binding, explicit registry/spec identity checks, and all supervised fallbacks.
- `tests/test_policy.py` proves `policy.go_binds` is removed while starting-state policy remains intact.
- `tests/test_author.py` and `tests/test_retro_box.py` prove Author is the sole caller and supplies config, journal events, specs directory, and `resolution.binds`.

## Verification
```
uv run pytest tests/test_baseline.py tests/test_policy.py tests/test_author.py tests/test_retro_box.py -q
uv run pytest -q
```

## Definition of rejected
Reject a second reader, global identity/spec lookup, exception from supervised
input, or a binding without a complete matching GO identity.

## Time budget
- expected: 75m
- stuck: 150m
