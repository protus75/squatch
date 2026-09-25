---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase2-exit
- daemon-scheduler
- seed-successor-proof

## Context
- squatch/tickets.py
- squatch/config.py
- config.yaml
- squatch/merge.py
- tests/test_seeded_phase2.py

## Plan contract
- section 20

## Goal
The first Phase 3 continuation authors the known-deep merge-queue construction seed and the next finite continuation as a reviewed, capped, dependency-ordered ticket-plane batch.

## Why
Section 20 is the one authoritative seed registry. `merge-queue` rides alone as the admission's only deliverable because it is KNOWN-DEEP; `phase3-continue-02` is the structural successor that carries the shrinking remainder. The batch test must prove the mechanical closure rules now, before either ticket can enter the drain: existing fenced files are Context, new-module ownership is stated from the registry, and the only `squatch/merge.py` hook is additive so no unfenced existing test has a contradicted assertion.

## Scope in
Author exactly `tickets/merge-queue/ticket.md` and `tickets/phase3-continue-02/ticket.md` as uncommitted `source: seed`, `state: confirmed` files, plus the committed batch test `tests/test_seeded_phase3_01.py`. `merge-queue` depends on `phase3-continue`, starts `high`/`high`, cites section 20 alone, and states that new `squatch/mergequeue.py` owns the dormant serial admission task, post-rebase re-gate orchestration, integration check, candidate tree-hash assertion, conflict-facts record, mechanical resolution rung, and typed unresolved-conflict handoff consumed by later Rework only after admission unwinds. Its Scope in carries a YAML `ownership` mapping naming that module and contract plus the existing `squatch/merge.py` hook `compose_merge_queue`. Its exact fence is `squatch/mergequeue.py`, `squatch/merge.py`, and `tests/test_mergequeue.py`; `squatch/merge.py` is existing Context. Construction leaves the current `Merge`, `Pipeline`, and `compose_pipeline` behavior unchanged and adds only that new dormant hook in the existing module, so no existing test assertion is flipped. `phase3-continue-02` depends on `merge-queue`, remains `medium`/`medium`, cites section 20 alone, owns only `tickets/` and `tests/test_seeded_phase3_02.py`, and carries the ordered suffix after `merge-queue` in the partition below. Its Context contains only paths already present on main when this ticket was authored.

The finite ordered admissions this continuation advances are:
```yaml
- [merge-queue]
- [rework-stage]
- [thresh-runtime]
- [dispatch-admission-boundary, dispatch-config-snapshot]
- [scheduler-activation]
- [merge-queue-activation, rework-activation]
- [background-consumers, control-inbox]
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

## Scope out
No implementation of the merge queue, Rework, activation, daemon, control surface, or any later Phase 3 deliverable. No seed beyond `merge-queue` and `phase3-continue-02`; no Phase 4 seed. No plan, production, config, or existing-test edit. No second ticket-plane writer and no Suggestion Box message.

## Scope fence
- tickets
- tests/test_seeded_phase3_01.py

## Acceptance criteria
- In `tests/test_seeded_phase3_01.py`, the authored set is exactly `merge-queue` and `phase3-continue-02`, both lint, carry `source: seed`, an initial `state: confirmed`, section 20 alone, the exact dependency edges above, and budgets at or under `drain.max_ticket_minutes`; the two-file batch is at or under `seeding.max_seeds_per_admission`.
- In `tests/test_seeded_phase3_01.py`, `merge-queue` is `high`/`high` with exact fence `squatch/mergequeue.py`, `squatch/merge.py`, `tests/test_mergequeue.py`, while `phase3-continue-02` is `medium`/`medium` with exact fence `tickets`, `tests/test_seeded_phase3_02.py` and carries the finite ordered YAML suffix above.
- In `tests/test_seeded_phase3_01.py`, each fence entry that is a file on main appears in that seed's `Context`, every Context entry exists on main, and the merge-queue seed's structured ownership record names `squatch/mergequeue.py` as owner of the registry's dormant serial admission contract.
- In `tests/test_seeded_phase3_01.py`, the merge-queue seed limits its existing `squatch/merge.py` change to the new additive `compose_merge_queue` hook; a scan over the pinned authoring-time `tests/*.py` path set records no reference to that new symbol, and the seed forbids changes to the tested `Merge`, `Pipeline`, and `compose_pipeline` behavior rather than contradicting an unfenced test.
- In `tests/test_seeded_phase3_01.py`, both authored seeds' production Implement renders fit requisition headroom with pinned bytes for every existing Context path.
- `uv run pytest tests/test_seeded_phase3_01.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_01.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if section 20's ordered suffix cannot be represented by these two seeds, if `merge-queue` requires an existing test change outside its registry fence, if either seed cannot pass requisition review or render headroom, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 75m
- stuck: 150m
