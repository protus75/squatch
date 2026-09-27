---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- flake-detection

## Context
- squatch/journal.py
- squatch/box.py
- squatch/daemon.py
- squatch/merge.py

## Plan contract
- section 20

## Goal
Release the exact quarantined test only after its report's fix merges and the test reruns green.

## Why
Mechanical release must bind the test, report, and fix-ticket identities, and persist before changing the ledger.

## Scope in
Extend the predecessor's `squatch/flake.py` and `tests/test_flake.py` boundary. They are owned by the prerequisite flake-detection seed and therefore omitted from authoring-time Context; its section 20 record contract is explicit here. Read the SAME ledger entry folded from `signal` key `flake/<box_id>` and body `{kind: flake_detected, test_id, signature, box_id}`, never a SHA-held set.

Resolve fix identity only when `Box.get(box_id).status == "authored"` and `Box.get(box_id).resolution.link == fix_stem` exactly. This authored-link resolution is produced by the merged `author-stage` path in `squatch/author.py`, which resolves the report through `Box.resolve` with `status="authored", link=authored.stem`. The embedded Box source defines that record shape; Message.status is a closed status, never the stem itself.

Require the existing journal `state_transition` to `merged` for that exact `fix_stem`, read through `squatch.journal`. `squatch/merge.py` is the emitter: the envelope carries `ticket=fix_stem`, with `body.to == "merged"` and body fields `run_seq`, `commit`, and `reviewed_sha`. It is read-only Context evidence, not a fence entry. Never infer merge from a stem name or from the box link alone.

The named test's green rerun is a separate typed explicit input supplied by the dormant hook's caller, binding `test_id` and `fix_stem` to the rerun outcome; production supply belongs to a later activation. The rerun is not inferred from resolution.link. Direct tests fabricate the merged transition in the emitter's shape and supply the typed rerun input.

When all prerequisites match that entry, append one `signal` keyed `flake-release/<box_id>/<fix_stem>` with body `{kind: flake_released, test_id, signature, box_id, fix_stem}` BEFORE folding the entry out of quarantine. Remove only that report/test entry. A second release of the same identity appends no event and changes no state. Manual `resume` remains the separate operator override; it is outside this mechanical boundary.

Compose the dormant boundary through a `compose_daemon_flake`-style hook in `squatch/daemon.py`; its direct proof lives in fenced `tests/test_flake.py`. No production composition in `squatch/__main__.py` or `squatch/drain.py` calls or constructs the hook; import reachability through `squatch/daemon.py` is allowed. Existing `tests/test_daemon_composition.py` tests are read-only preservation evidence, with no requested migration.

## Scope out
Do not activate production callers, execute tests from the hook, implement manual resume, add a new box resolution schema, or migrate production composition tests. Do not alter detection's event contract or substitute SHA state.

## Scope fence
- squatch/flake.py
- tests/test_flake.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_flake.py`: Direct tests bind the SAME ledger entry to the authored box's exact fix link, that fix's merged journal transition, and the named test's typed green rerun. Fabricate the transition emitted by `squatch/merge.py`: envelope `ticket=fix_stem`, `body.to == "merged"`, and `run_seq`, `commit`, and `reviewed_sha`.
- `tests/test_flake.py`: Prove one no-release case per prerequisite: wrong box status, link mismatch, unmerged stem, and missing or red rerun. A rerun for another test or fix must not release the entry. Each refusal preserves all events and ledger state.
- `tests/test_flake.py`: Assert the exact `signal` key `flake-release/<box_id>/<fix_stem>` and body `{kind: flake_released, test_id, signature, box_id, fix_stem}` BEFORE folding the entry out of quarantine. Observe append-before-removal ordering and append-before-removal reconstruction after interruption; unrelated entries remain intact.
- `tests/test_flake.py`: A second release of the same identity appends no event and changes no state, including after reconstruction.
- Direct hook tests in `tests/test_flake.py` exercise the real component. No production composition in `squatch/__main__.py` or `squatch/drain.py` calls or constructs the hook; import reachability through `squatch/daemon.py` is allowed. Prove call-path dormancy with a source/AST call check that fails if either production root constructs or calls the hook. No SHA-held set substitutes for the test/report ledger identities.

## Verification
```
uv run pytest tests/test_flake.py -q
uv run pytest tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the boundary needs production activation, a SHA-held substitute, an unfenced edit, or an on-demand Context exception for an existing fence path. Report premise_failed naming the missing owner; never widen the fence.

## Time budget
- expected: 75m
- stuck: 150m

