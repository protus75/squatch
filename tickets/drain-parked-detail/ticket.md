---
kind: feature
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/drain.py
- squatch/runner.py
- squatch/diagnose.py
- tests/test_drain.py

## Goal
`Drain._tail`'s `parked:` line for a still-parked stem names that stem's latest terminal `reason` (built from the terminal's `finding_codes`) instead of only the ended outcome name. When the terminal recorded a harvested attempt, the line also points at `tickets/<stem>/attempts/<run_seq>/`, and when `tickets/<stem>/diagnosis.json` is on disk it names that path too. `checks.json` and `review.md` keep being listed when present. A parked `infra_error` or `timeout` stem with neither `checks.json` nor `review.md` on disk still gets its attempt directory and reason named, so the engine log is never its only pointer.

## Why
`Runner._finish_delivery`'s `stopped:` line already names the harvested attempt directory for every non-settled run, and the same terminal `state_transition` body already carries `reason` and `finding_codes`; `diagnosis.json` is already lifted into the ticket plane for every such terminal. `Drain._tail` (`squatch/drain.py`) only probes for `checks.json`/`review.md` through `_artifacts`, so a parked `infra_error` or `timeout` stem -- which usually has neither -- sends the operator to the engine log even though its findings and diagnosis lessons already sit in the ticket plane. The data this needs is already on the terminal and on disk, so no seam change is required.

## Scope in
- `squatch/drain.py`: `Drain._tail` reads the parked stem's `facts.terminals[stem]` to name its `reason`, and names `tickets/<stem>/attempts/<run_seq>/` when that terminal's `harvest` field is set.
- `squatch/drain.py`: `Drain._artifacts` (or an equivalent on-disk check `_tail` uses) also lists `tickets/<stem>/diagnosis.json` when that file exists, alongside the existing `checks.json`/`review.md` check.
- `squatch/drain.py`: the `parked:` line's wording keeps naming `self._runner.log_path` alongside the new pointers, never replacing it.
- `tests/test_drain.py`: two new tests pin a gate-failed park (with `checks.json`, `review.md`, `diagnosis.json` on disk and a harvested attempt) and an infra-error park (with no `checks.json`/`review.md` on disk, but a harvested attempt and a `reason`).

## Scope out
- `squatch/runner.py` and the terminal `state_transition` body shape -- `reason`, `finding_codes`, and `harvest` are already written; unchanged.
- The cap-spent, premise-park, and retry-budget paved-road wording already in `_tail` -- unchanged for a park with no harvested attempt.
- `_eligible`, `_reoffers`, and every other dispatch-ordering path in `squatch/drain.py` -- unchanged.
- Any notify/escalation transport -- the `parked:` line is a `status`-adjacent report line, not an escalation.

## Scope fence
- squatch/drain.py
- tests/test_drain.py

## Acceptance criteria
- A parked stem's `parked:` line names the stem's latest terminal `reason` instead of only the ended outcome name (checked by `pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q`).
- When that terminal's `harvest` field names an attempt, the `parked:` line names `tickets/<stem>/attempts/<run_seq>/` (checked by the same `pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q`).
- When `tickets/<stem>/checks.json` or `tickets/<stem>/review.md` exists on disk for the parked stem, the `parked:` line still lists it, exactly as before this change (checked by `pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q`).
- When `tickets/<stem>/diagnosis.json` exists on disk for a parked stem, the `parked:` line names that path, checked by `pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q`.
- A parked stem whose latest terminal is `infra_error` or `timeout`, with no `checks.json` and no `review.md` on disk, still gets its attempt directory and `reason` named in the `parked:` line (checked by `pytest tests/test_drain.py::test_an_infra_error_park_with_no_checks_or_review_still_names_its_attempt_directory_and_reason -q`).
- `self._runner.log_path` is still named in the `parked:` line alongside the new pointers (checked by both `pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q` and `pytest tests/test_drain.py::test_an_infra_error_park_with_no_checks_or_review_still_names_its_attempt_directory_and_reason -q`).
- The existing cap-spent and premise-park `parked:`/`reject queue:` wording is unchanged (checked by `pytest tests/test_drain.py -q`).

## Verification
```
pytest tests/test_drain.py::test_a_gate_failed_park_names_its_reason_and_harvested_attempt_directory -q
pytest tests/test_drain.py::test_an_infra_error_park_with_no_checks_or_review_still_names_its_attempt_directory_and_reason -q
pytest tests/test_drain.py -q
```

## Definition of rejected
Stop and throw the branch away if naming the reason, attempt directory, or diagnosis path turns out to require a new field on the `state_transition` body or any other seam widening beyond reading `facts.terminals[stem]` and probing `tickets/<stem>/` for existing files -- that would falsify this ticket's premise that no seam change is required, and belongs in a Suggestion Box item against `squatch/runner.py`, not a scope-fence expansion here.

## Time budget
- expected: 25m
- stuck: 60m
