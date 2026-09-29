---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- core-drift-classifier

## Context
- squatch/hostfiles.py
- squatch/gates.py
- squatch/config.py
- tests/test_hostfiles.py

## Plan contract
- section 20

## Goal
Activate the closed managed-conduct drift gate.

## Why
The pure renderer and classifier must become a merge-time hard boundary without
duplicating the routing-to-conduct-file policy.

## Scope in
Activate the engine-shipped hard `core_drift` gate on conduct-file paths
resolved from routing. Compare every committed managed block with a fresh
branch-version render, preserve the project-owned remainder, refuse malformed,
duplicate, or partial marker text, and join the merge-time mechanical rerun
set.

Move the complete routing-to-conduct-file resolver from inline `_core` logic
into one `squatch/providers.py` function. Both `_core` and `core_drift` call
that function; the provider-to-`CLAUDE.md`/`AGENTS.md` mapping has one owner
and no copied path. Replace
`test_classifier_is_unreachable_from_production_gates` with coverage proving
the gate reaches `hostfiles.classify` and both invokers share the resolver.
Keep `test_rendering_has_no_git_or_commit_effect`; `squatch/hostfiles.py`
retains its exact pure import set.

`squatch/merge.py`, `squatch/providers.py`, `squatch/__main__.py`,
`tests/test_gates.py`, `tests/test_merge.py`, `tests/test_providers.py`, and
`tests/test_cli.py` are measured on-demand inspection exceptions. Every other
existing fence path is Context. No new Context path is invented.

## Scope out
Do not add another resolver, relax marker refusal, change project-owned bytes,
or implement any later Phase 6 payload.

## Scope fence
- squatch/hostfiles.py
- squatch/gates.py
- squatch/config.py
- squatch/merge.py
- squatch/providers.py
- squatch/__main__.py
- tests/test_hostfiles.py
- tests/test_gates.py
- tests/test_merge.py
- tests/test_providers.py
- tests/test_cli.py

## Acceptance criteria
- `tests/test_gates.py` proves the hard `core_drift` gate reaches `hostfiles.classify` through the shared resolver.
- `tests/test_hostfiles.py` proves the gate compares a fresh branch render, preserves the project remainder, and refuses malformed marker forms.
- `tests/test_merge.py` proves merge-time mechanical reruns include the gate while `tests/test_hostfiles.py` preserves renderer Git/commit purity.

## Verification
```
uv run pytest tests/test_hostfiles.py tests/test_gates.py tests/test_merge.py tests/test_providers.py tests/test_cli.py -q
uv run pytest -q
```

## Definition of rejected
Reject a copied resolver, an unreachable gate, permissive marker handling, or a
missing merge-time rerun.

## Time budget
- expected: 75m
- stuck: 150m
