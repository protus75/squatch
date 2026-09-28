---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- retro-drain-invoker

## Context
- squatch/box.py
- tests/test_box.py
- squatch/author.py
- tests/test_seeded_phase4_02.py

## Plan contract
- section 20

## Goal
Activate retro proposals through Box, Author, and Merge with journaled tombstone
reopen and provenance boundaries.

## Why
Retro findings need stable proposal identities and a fail-closed, replay-stable
route from report to authored ticket to merged prompt-spec change.

## Scope in
Extend the predecessor `squatch/retro.py` output into one `retro_finding` per
proposal carrying `retro_report_key`, `fixed_failure`, `overcorrection_risk`,
and `proposed_spec_paths`. Define
`proposal_id = sha256(canonical_json(retro_report_key, fixed_failure, overcorrection_risk, sorted(proposed_spec_paths)))[:16]`
and Box origin `retro-proposal/<retro_report_key>/<proposal_id>`. Box signatures
include origin, so replay dedups the same proposal while numeric or spec-path-only
differences stay distinct.

Box owns one `record_rereport` path used by both enqueue-signature hits and the
semantic-triage tombstone match. At K=3, call the journal-backed callback to
append an existing-type `signal` event keyed exactly
`tombstone-reopen/<box_id>/<reports>` with body exactly
`{kind: tombstone_auto_reopened, box_id, signature, reports}` BEFORE clearing
the resolution. `reports` is the post-increment count and `signature` is the
matched stable Box signature. Then mark the record
`reopened_from_tombstone: true`.

Every production Box constructor in the fenced merge, stage, runner, daemon,
drain, serve, status, and CLI paths that has journal access receives the
callback, including Merge's existing Box construction. Preserve Merge's
Verification and base-failure filing behavior; its Box is never consulted for
retro provenance. The standalone `python -m squatch.box ingest` constructor has
no callback: it counts the rereport, refuses to clear a K=3 tombstone, and raises
named `RereportCallbackRequired` with paved road exactly
`rerun through a journal-backed Squatch command`.

Triage and Author pass the reopen marker to `policy.starting_state`, which forces
`draft` regardless of the normal message-class row. Clear the one-shot marker
only after authoring succeeds. Authoring from `retro_finding` appends one bridge
`signal` keyed `retro-ticket/<ticket-stem>` with body exactly
`{kind: retro_ticket_authored, box_id, retro_report_key, ticket_stem}` before the
authored-ticket resolution is committed.

The journal bridge is the sole retro-provenance lookup. At the existing
successful admission point in `squatch/merge.py`, after the real squash SHA and
changed paths are known but before the merged terminal is journaled, handle only
a ticket whose source is exactly `box:retro_finding`, whose admitted diff changes
at least one path under `specs/` ending in `.md`, and whose unique
`retro_ticket_authored` bridge exists. Append one `signal` keyed
`retro-prompt-spec-change/<ticket-stem>/<squash-sha>` with body exactly
`{kind: retro_prompt_spec_change_merged, box_id, retro_report_key, ticket_stem, squash_sha, changed_spec_paths}`.
`changed_spec_paths` is the sorted non-empty tuple of matching paths. The key
provides replay idempotence; a missing or ambiguous bridge is a hard merge
finding.

The fenced measured on-demand inspection exceptions are `squatch/merge.py`,
`squatch/triage.py`, `squatch/policy.py`, `squatch/stages.py`,
`squatch/runner.py`, `squatch/daemon.py`, `squatch/drain.py`,
`squatch/serve.py`, `squatch/status.py`, `squatch/__main__.py`,
`tests/test_merge.py`, `tests/test_author.py`, `tests/test_triage.py`,
`tests/test_policy.py`, `tests/test_stages.py`,
`tests/test_daemon_composition.py`, `tests/test_drain.py`, and
`tests/test_serve.py`.

Predecessor-new `squatch/retro.py` is fenced but excluded
from authoring-time Context, as is `tests/test_retro.py`. `tests/test_status.py`
does not yet exist and is excluded from this activation fence.

## Scope out
Do not infer retro provenance from Box or a stem, add a journal event type, clear
a tombstone before its signal, reopen without a callback, retain the draft
override after successful authoring, or change Merge's base-failure route.

## Scope fence
- squatch/retro.py
- squatch/box.py
- squatch/merge.py
- squatch/author.py
- squatch/triage.py
- squatch/policy.py
- squatch/stages.py
- squatch/runner.py
- squatch/daemon.py
- squatch/drain.py
- squatch/serve.py
- squatch/status.py
- squatch/__main__.py
- tests/test_box.py
- tests/test_merge.py
- tests/test_author.py
- tests/test_triage.py
- tests/test_policy.py
- tests/test_stages.py
- tests/test_daemon_composition.py
- tests/test_drain.py
- tests/test_serve.py
- tests/test_retro_box.py

## Acceptance criteria
- `tests/test_retro_box.py` proves the exact proposal SHA-256 identity and origin, replay dedup, numeric/path distinction, and the shared enqueue/semantic-triage `record_rereport` route.
- `tests/test_retro_box.py` proves K=3 appends the exact replay-stable `signal` key and body before clearing, every production Box with journal access receives the callback including Merge, and Merge keeps Verification/base-failure behavior without Box provenance lookup.
- `tests/test_retro_box.py` proves no-callback ingest counts the rereport, keeps the tombstone, and raises `RereportCallbackRequired` with the exact paved road.
- `tests/test_retro_box.py` proves journal-before-reopen, the one-shot draft override, the exact Author bridge, journal-only Merge lookup, source/path predicates, exact successful-merge signal body and key, replay idempotence, and hard findings for missing or ambiguous provenance.
- `uv run pytest -q` proves all fenced composition roots and predecessor suites use the callback without changing unrelated behavior.

## Verification
```
uv run pytest tests/test_retro_box.py tests/test_box.py tests/test_merge.py tests/test_author.py tests/test_triage.py tests/test_policy.py tests/test_stages.py tests/test_daemon_composition.py tests/test_drain.py tests/test_serve.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unstable proposal identity, split rereport routes, an unjournaled or
post-clear reopen, any production Box with journal access but no callback,
no-callback tombstone clearing, persistent draft override, Box-derived retro
provenance, or a merge signal outside the exact successful predicate.

## Time budget
- expected: 75m
- stuck: 150m
