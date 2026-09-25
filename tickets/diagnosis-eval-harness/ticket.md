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
- spine-diagnosis

## Context
- eval/harness.py
- tests/test_eval_harness.py
- eval/fixtures/logic-inverted-guard-add-invoice/expected.json
- squatch/llm.py
- squatch/llmeffect.py
- squatch/driver.py
- squatch/effects.py
- squatch/journal.py
- squatch/providers.py
- squatch/config.py
- squatch/redact.py
- squatch/seams.py
- tests/test_llm_effect.py

## Plan contract
- section 11
- section 6
- section 8
- section 15

## Goal
The diagnosis real-model eval's machinery is merged and reviewed before anything pays for it: `eval/diagnose.py` drives the production `diagnose` stage over a committed fixture set of failed attempts, scores agreement with each fixture's expected verdict, enforces a per-call stuck budget by hard kill and a flat per-run USD cap checked before every call, writes one closed-schema report artifact, and every expected verdict is proven reachable under the fake LLM by tests that read that report.

## Why
Section 19 splits the diagnosis eval into two chained deliverables so the spend-deciding code never runs unreviewed on the first paid call: this ticket is the harness and fixtures, the next seed only executes them. The review-baseline harness (`eval/harness.py`) is the precedent -- fixtures with a hidden answer key authored by a (provider, model) different from the surface under test, a run through the one LLM-stage driver and the provider layer, refuse-before-call checks, a recorded summary -- and this harness follows its shape rather than inventing a second one. The diagnosis surface is judgment the deterministic ladder routes on (section 11.4): a diagnoser that answers `retry` to an impossible ticket, or `reject` to a fixable oversight, spends the lineage's caps on the wrong rung, so its agreement rate is the signal the plan wants before the ladder trusts it. Budget and timeout enforcement are pinned here, under the fake, because the first real run must not be the first test of the kill or of the cap.

## Scope in
A new module `eval/diagnose.py`, run as `uv run python -m eval.diagnose` from a checkout root, that drives the PRODUCTION diagnosis stage -- `diagnose_stage` from `squatch/diagnose.py` over `specs/diagnose.md`, both unchanged, resolved through `Registry` at the spec's tier (the eval owns no ticket) -- over every fixture directory under `eval/diagnose_fixtures/<name>/`, each holding exactly `ticket.md` (the failed ticket), `harvest.json` (validating as the `Harvest` model of `squatch/harvest.py`), `expected.json`, and optionally `run.md`; every fixture is refused fail-closed on a missing file, an invalid answer key, or a harvest that does not validate. `expected.json` is a closed pydantic schema: `schema_version` 1, `expected_verdict` in `VERDICTS`, `failure_class` in the closed set `fixable_oversight | under_capability | oversized | false_premise | environment`, mapped one-to-one onto `retry | escalate | split | reject | abandon-human` and refused when the pair disagrees, `rationale` (one sentence the answer key gives, never shown to the model), and `author` (provider, model, tier) -- authored by a (provider, model) DIFFERENT from the one routed to `diagnose` at the exercised tier, at minimum a different tier, refused before any call when they coincide (section 6: same-family fixtures share the surface's blind spots). The committed set holds at least 12 fixtures with at least two per verdict, each a realistic failed attempt: the harvest's outcome, findings, reason, `diff --stat`, and spool tails must actually support the expected verdict, and every planted defect class of the review baseline may be reused as material. Each fixture is one driver run through `LLMEffect` under `Effects` over a HARNESS-OWNED journal at `--state` (default `<config.state_dir>/eval-diagnose/`, instance-local and gitignored with the state dir) -- never the instance journal and never the instance lock, because the spend seed runs this harness inside a drain-dispatched implement worktree while the drain holds the writer lock -- with the effect key carrying the fixture name as its stem and a run sequence equal to the count of prior completion signals in that journal, so a re-run after a stopped run replays the fixtures it completed at no cost and calls only the rest, while a re-run after a completed run takes fresh keys. Scoring per fixture: outcome, verdict (null when no schema-valid `Diagnosis` came back after the driver's one bounded re-prompt, `DIAGNOSE_RETRY_CAP`), `agreed` (verdict equals expected), lesson count, usd, provider, model; summary: fixtures, scored, agreed, `agreement_rate` over the scored fixtures, per-verdict agreement, unscored count, total usd. Two engine constants enforce the bounds: `STUCK_SECONDS` = 600, the per-call stuck budget on the `LLMEffect` -- a call that outlives it is hard-killed through `abort_current` BEFORE anything records, so the harness journal holds that call's intent and no completion, the fixture scores `timeout` (unscored), and the run continues with the next fixture; and `USD_CAP` = 5.00, the flat per-run USD cap checked PRE-CALL: before each fixture's call the harness refuses when `spent + estimate > USD_CAP`, where `spent` is the sum of this run's completion costs and `estimate` is the largest single-call usd this run has seen, else the routed provider's `limits.est_cost_per_call_usd`, else 0 -- on refusal no call is made, the report records `stopped: budget` and lists every fixture not run, and no completion signal is journaled so the next run replays and continues. The report is the artifact: `DiagnosisEvalReport`, a closed pydantic schema -- `schema_version` 1, `produced_at_sha` (the checkout HEAD), `identity` (provider, model, tier serving `diagnose`), `spec_version`, `fixture_authors`, `usd_cap`, `stuck_seconds`, `stopped` (null or `budget`), `scores`, `summary` -- written as JSON to `--report <path>` (required), and a completed run (every fixture reached a terminal, `stopped` null) also appends one `signal` of kind `diagnosis_eval` to the harness journal carrying the summary, the identity, and the report path. `--check <path>` validates an existing report against the schema, prints its summary, and exits 0 (valid) or 1 (invalid) with no model call; `main` exits 1 on any refusal with the paved road printed, exactly as `eval/harness.py` does. Tests in `tests/test_eval_diagnose.py`, all offline against `FakeLLM`.

## Scope out
No change to `squatch/`, `specs/`, `eval/harness.py`, or the review fixtures under `eval/fixtures/`: the harness consumes the production stage builder, spec, and `Harvest` model as merged, and a gap in them is answered `premise_failed`, never patched here. No real-model call in this ticket's tests or verification; the paid run is the next seed. No GO or NO-GO verdict, no journal signal on the instance journal, no lane-writer registration of the report (that registry lands with the battery report seed), no `--record-go` mode, no fixture generation from live runs, no scoring of `lessons` text. No second harness shape: the refuse-before-call checks, driver use, and scoring idiom mirror `eval/harness.py`.

## Scope fence
- eval/diagnose.py
- eval/diagnose_fixtures/
- tests/test_eval_diagnose.py

## Acceptance criteria
- In `tests/test_eval_diagnose.py`, the committed set under `eval/diagnose_fixtures/` loads with at least 12 fixtures and at least two per verdict, every `harvest.json` validates as `Harvest`, every `expected.json` pairs its `failure_class` with its verdict, and a fixture with a missing file, a harvest that does not validate, or a class-verdict mismatch is refused with a message naming the fixture.
- In `tests/test_eval_diagnose.py`, `specs/diagnose.md` renders every committed fixture through `diagnose_stage` with the ticket, harvest, and (when present) run record inside data blocks.
- In `tests/test_eval_diagnose.py`, a `FakeLLM` scripted with each fixture's expected verdict yields a report with `agreement_rate` 1.0, every fixture `agreed`, `stopped` null, and one `diagnosis_eval` signal in the harness journal -- every expected verdict reachable through the production `Diagnosis` schema.
- In `tests/test_eval_diagnose.py`, a reply outside the verdict vocabulary is re-prompted exactly once and then scored with verdict null and `agreed` false, and the run still completes.
- In `tests/test_eval_diagnose.py`, under a small `stuck_seconds` a fixture scripted as a resisting `Hang` is aborted (`FakeLLM.aborted` is 1), the harness journal holds that call's `effect_intent` with no `effect_completion`, the report scores it `timeout` and unscored, and the remaining fixtures are still scored.
- In `tests/test_eval_diagnose.py`, with scripted per-call costs that cross the cap, the fake receives exactly as many requests as the cap admits, the report carries `stopped: budget`, lists every fixture not run, and `summary.usd` is at most `USD_CAP`; a second run over the same `--state` replays the completed fixtures (the fake receives only the remaining requests) and completes.
- In `tests/test_eval_diagnose.py`, `USD_CAP` equals 5.0 and `STUCK_SECONDS` equals 600.
- In `tests/test_eval_diagnose.py`, `--check` exits 0 on a report the run wrote and 1 on a report with a field outside the schema, and `main` exits 1 before any call on a placeholder routing row and on a fixture author identical to the diagnose identity at the exercised tier.
- `uv run pytest tests/test_eval_diagnose.py -q` exits 0 and makes no network or subprocess call other than `git rev-parse`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_eval_diagnose.py -q
uv run python -m eval.diagnose --help
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if `diagnose_stage`, `DiagnosisInput`, or `Harvest` as merged cannot be driven from a ticket-less harness without a change under `squatch/` or `specs/`, if the stuck kill cannot be exercised through `LLMEffect` and `FakeLLM.abort_current` as they stand, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
