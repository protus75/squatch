---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- requisition-review-seed

## Context
- squatch/journal.py
- squatch/artifacts.py
- squatch/config.py
- squatch/git.py
- squatch/effects.py
- tests/test_journal.py
- tests/test_effects.py
- tests/test_terminal.py

## Plan contract
- section 15
- section 6
- section 11
- section 19

## Goal
The invariant auditor exists as a pure fold over the journal: `squatch/audit.py` declares the closed set of section 15 invariants, each carrying the law it enforces, folds them over an event stream into typed violations, and a module entry audits an instance journal with the section 18 exit-code contract; it is green over every journal the merged suite's pipeline runs write, and its own Check-lane `checks.json` is the green proof the phase exit reads.

## Why
Section 15's test-harness ladder starts at rung 1, the invariant auditor run over the journal, and rung 4 -- fake-agent simulation driving whole pipelines through the injected seams, the shape of the Phase 2 shakeout battery -- names the auditor as its pass condition, so the auditor lands before the battery's first group. Section 6 pins the vocabulary it validates against: the closed `EventType` set, the promoted `to` field's run-state vocabulary, the once-semantics pairing of intents and completions. Section 15 fixes the pairing invariant's scope exactly -- it fires at `merged` and NOWHERE else, every non-ok terminal is closed-run history and a run with no terminal is reconcile's orphan -- because a broader reading reddens every legitimate failure. Section 19 puts the green proof in the ordinary Check lane: this ticket's own `## Verification` runs the auditor's tests, the Check lane lifts `checks.json`, and the exit ticket reads that committed artifact -- never a self-attested green. It depends on `requisition-review-seed` so the record it audits is the whole merged spine's, seed lifts included.

## Scope in
A new module `squatch/audit.py` owning: `Violation` (a closed pydantic model: `invariant`, `ticket`, `run_seq`, `message`); `INVARIANTS`, an ordered tuple of `Invariant(name, law, check)` where `law` is the one-sentence rule and `check(segments) -> list[Violation]` is pure over an ordered iterable of ordered event iterables -- exactly these, in this order: `one_terminal_per_run` (per stem and `run_seq`, at most one terminal `state_transition` after its `running`; a `running` with none is never a violation); `declared_caps` (every `cap_consumed` names a cap in the `caps:` vocabulary of `squatch/caps.py`); `effects_paired_at_merged` (for every run whose terminal is `to: merged`, every `effect_intent` in that run has a matching `effect_completion` by key; every other terminal and every terminal-less run is exempt); `merged_carries_commit` (every `to: merged` body carries a `commit`, null only when its `reviewed_sha` is also null -- the `already_satisfied` no-op settlement of section 5); `closed_run_states` (every `state_transition` body's `to` is in `RUN_STATES`); `closed_event_types` (every event `type` is in the journal's `EVENT_TYPES`); `ts_monotone` (timestamps non-decreasing within each supplied segment, compared as the pinned RFC 3339 strings); `audit(segments) -> tuple[Violation, ...]` running every invariant; `audit_journal(state_dir) -> tuple[Violation, ...]` reading through the additive `Journal.read_segments()` seam so corruption surfaces as the journal's own refusal, never a skipped line. `Journal.read_segments()` yields each ordered journal segment as its own ordered event tuple under the same corruption and active-tail rules as `Journal.read()`, and `Journal.read()` flattens `read_segments()` so parsing has one owner. The module entry `uv run python -m squatch.audit [--state <dir>]` resolves the instance state dir exactly as `squatch/box.py`'s entry does (the parent checkout's `config.yaml` through `squatch/git.py`), prints each violation on one line, and exits 0 green, 1 with violations, 2 on a refusal with a paved road; it takes no lock (a read-only projection, D3). Tests for every rule above in `tests/test_audit.py`: one refusal fixture per invariant, a green fixture, and a green run over the journals the existing `tests/test_terminal.py` pipeline fixtures write. Read `squatch/caps.py` and `squatch/box.py` in the worktree (they land with the `depends` and did not exist when this seed was authored).

## Scope out
No new journal event, no auditor output into the journal, no gate, no CLI verb (the verb list is closed, section 18; this is a module entry like the box's ingestion). No live-run watcher (the continuous form rides the Phase 3 daemon). No repair, no compaction, no tolerance of a corrupt segment. No change to `squatch/stages.py`, any stage, or any test claim; the only journal change is the additive segment-preserving read seam above. This ticket authors and commits NO `checks.json` -- the Check lane produces it over the merged code.

## Scope fence
- squatch/audit.py
- squatch/journal.py
- tests/test_audit.py
- tests/test_journal.py

## Acceptance criteria
- In `tests/test_audit.py`, `INVARIANTS` names exactly `one_terminal_per_run`, `declared_caps`, `effects_paired_at_merged`, `merged_carries_commit`, `closed_run_states`, `closed_event_types`, `ts_monotone` in that order, each with a non-empty `law`.
- In `tests/test_audit.py`, each invariant has one fixture stream it flags with exactly one `Violation` naming it, and the green fixture -- a merged run with paired effects, a `gate_failed` run with an unpaired intent, a `running` with no terminal, and an `already_satisfied` merge with null `commit` and null `reviewed_sha` -- yields no violation.
- In `tests/test_audit.py`, `effects_paired_at_merged` flags a merged run with an unpaired intent and never flags an unpaired intent in a `timeout`, `abandoned`, `rejected`, `gate_failed`, or `premise_failed` run.
- In `tests/test_journal.py`, `Journal.read_segments()` preserves two pre-seeded segment boundaries in filename order, applies the existing torn-tail tolerance only to the active segment, and `Journal.read()` returns the same events flattened in order.
- In `tests/test_audit.py`, `audit_journal` over a state dir whose rolled segment holds a malformed line raises the journal's corruption error rather than returning violations.
- In `tests/test_audit.py`, `audit` is green over the journal written by a full fake-pipeline run that merges and by one that ends `gate_failed`, both driven through the production `Runner`.
- In `tests/test_audit.py`, the module entry `uv run python -m squatch.audit --state <dir>` exits 0 over a green journal, 1 over one with a violation printing the invariant name, and 2 with a paved road on a missing state dir.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_audit.py -q
uv run pytest tests/test_journal.py -q
uv run python -m squatch.audit --help
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the cap vocabulary of `squatch/caps.py` cannot be imported without a config, if the segment-preserving reader cannot share the existing parser and corruption rules with `Journal.read()`, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
