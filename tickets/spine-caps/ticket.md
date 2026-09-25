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
- none

## Context
- squatch/drain.py
- squatch/runner.py
- squatch/driver.py
- squatch/config.py
- squatch/effects.py
- squatch/artifacts.py
- tests/test_drain.py
- tests/test_terminal.py

## Plan contract
- section 11
- section 6
- section 9
- section 15

## Goal
The failure-spine caps `diagnosis` and `infra` are live beside the shipped `retry` cap: one cap vocabulary, one `cap_consumed` writer, one lineage-scoped per-cap journal fold, an `infra` draw on every `infra_error` and `timeout` terminal, and a pre-dispatch check that parks a stem at any spent cap with the cap named verbatim.

## Why
Section 11.1: caps fire first, before any model call, and every non-ok terminal draws from one NAMED budget so no failure class loops outside the cap system. Today only `retry` is folded and drawn (the Phase 1 drain), so a crashing review call or a hung subprocess is re-offered until the retry cap alone runs out and a spent cap is reported generically. The diagnosis call (the next seed batch) needs a `diagnosis` budget and a pre-call check to draw against; it must not invent its own. Section 9's ownership law puts a cap draw with the module that journals its `cap_consumed` event, so this ticket lands ONE writer and ONE fold and re-points the drain's retry accounting onto them in place -- never a second path. The `premise_bounce` cap is NOT this ticket: a hold never lands before its release, and its release (the escalation ladder and the Reject queue verdict verbs) lands in a later batch (section 2).

## Scope in
A new module `squatch/caps.py` owning: the closed cap vocabulary as constants whose names are exactly the keys of the `caps:` config block (`squatch/config.py` `Caps`); the ONE `cap_consumed` writer (body: `cap`, `ticket_sha` = the blob sha of the committed `tickets/<stem>/ticket.md`, `run_seq`) that the drain's retry draw and the runner's infra draw both call; the ONE lineage fold, a per-cap count of the stem's `cap_consumed` events naming THAT cap (a draw naming another cap never counts; a draw with no `ticket_sha` counts against the current budget); `remaining(config, events, stem, cap)`; and `spent(config, events, stem)` returning the verbatim reason `<cap> cap spent (<drawn> of <budget> drawn)` for the first spent cap among the spine caps this batch serves (`retry`, `diagnosis`, `infra`), else `None`. `squatch/drain.py` re-points `RETRY_CAP`, `Fold.retry_drawn`, `retry_budget`, and `_draw_retry` onto that module (rename in place, every call site in this change) and refuses a re-offer at ANY spent spine cap, the parked report line carrying the `spent` reason verbatim. `squatch/runner.py` draws one `infra` unit through the writer on every `infra_error` and `timeout` outcome, BEFORE the run's terminal `state_transition` is appended (the section 11.2 handler order: the terminal carries the final cap state). `squatch/driver.py` re-points its `RETRY_CAP` onto the vocabulary. `squatch/config.py` refuses a config whose `caps.retry` exceeds `caps.diagnosis` with a finding naming both keys (section 11.1: retry is never set above diagnosis). Tests for every rule above.

## Scope out
No diagnosis call, no `lessons`, no escalation ladder, no Reject queue, no `confirm`/`reject` verbs, no `premise_bounce` draw (all later seeds). No operator-keep bound on the fold: the `confirm` keep signal that bounds it (section 11.2) lands with the Reject queue seeds, and the fold gains that bound there; this fold counts every draw on the lineage. No drought exemption: no drought producer exists yet (breakers and quota cooldowns are Phase 3-4), so every `infra_error` and `timeout` draws; the exemption keys on the drought reason class and lands with its first producer. No change to the driver's in-stage re-prompt allowance (`Driver.retry_cap`), to harvest, to the worktree lifecycle, to `Pipeline.run`'s return type, or to `specs/`. No new frontmatter field, no new config key, no new journal event type: `cap_consumed` already exists, and its body keeps the shape the Phase 1 drain writes.

## Scope fence
- squatch/caps.py
- squatch/drain.py
- squatch/runner.py
- squatch/driver.py
- squatch/config.py
- tests/test_caps.py
- tests/test_drain.py
- tests/test_terminal.py
- tests/test_config.py
- tests/test_driver.py

## Acceptance criteria
- `squatch/caps.py` declares the cap vocabulary, and a test in `tests/test_caps.py` asserts the declared names equal the field names of `Caps` in `squatch/config.py` exactly.
- In `tests/test_caps.py`, the fold over a journal holding two `retry` draws and one `infra` draw for one stem reports `retry` drawn 2 and `infra` drawn 1, and a `diagnosis` draw of 0.
- In `tests/test_caps.py`, a `cap_consumed` event with no `ticket_sha` counts toward its cap's drawn total, and draws recorded under two different `ticket_sha` values for one stem count toward the same total.
- In `tests/test_caps.py`, `spent` returns exactly `infra cap spent (6 of 6 drawn)` for a stem with six `infra` draws under the shipped defaults, and `None` for a stem with remaining budget on every spine cap.
- In `tests/test_terminal.py`, a run ending `infra_error` journals one `cap_consumed` event with body `cap: infra`, `ticket_sha` equal to the committed ticket blob sha, and `run_seq` equal to the run's, and that event precedes the run's terminal `state_transition` in the journal; a run ending `timeout` does the same; a run ending `gate_failed` journals no `infra` draw.
- In `tests/test_drain.py`, a stem whose `infra` cap is spent (config `caps: {infra: 1}`, one `infra_error` run) is never re-offered, the drain's parked line contains `infra cap spent (1 of 1 drawn)`, and the drain still exits 0.
- In `tests/test_drain.py`, every Phase 1 retry claim still holds: one retry draw per re-offer with `ticket_sha` and `run_seq`, `retry cap spent (1 of 1 drawn)` reported at the spent cap, and a foreign-cap draw never reducing the retry budget.
- In `tests/test_config.py`, a config with `caps: {retry: 7, diagnosis: 6}` is refused with a finding that names both `caps.retry` and `caps.diagnosis`, and a config with `caps: {retry: 6, diagnosis: 6}` loads.
- `grep -rn "RETRY_CAP = " squatch` reports exactly one definition, in `squatch/caps.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_caps.py -q
uv run pytest tests/test_drain.py tests/test_terminal.py tests/test_config.py tests/test_driver.py -q
grep -rn "RETRY_CAP = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the infra draw cannot be placed in `squatch/runner.py` without changing `Pipeline.run`'s return type, if the fold cannot serve the drain's retry accounting without a second retry-specific fold surviving beside it, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
