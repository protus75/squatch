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
- spine-harvest

## Context
- squatch/runner.py
- squatch/merge.py
- squatch/stages.py
- squatch/driver.py
- squatch/drain.py
- squatch/artifacts.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_driver.py
- tests/test_cli.py
- tests/test_drain_upgrade.py
- tests/test_reconcile.py

## Plan contract
- section 11
- section 5
- section 6
- section 8

## Goal
Every diagnosable non-ok terminal carries the failure spine's one model judgment: a diagnosis call over the harvested material runs between harvest and the terminal write, its closed verdict and typed `lessons` ride the run's terminal `state_transition` and `tickets/<stem>/diagnosis.json`, the next attempt's prior-attempts block renders a diagnosed attempt's lessons in place of its raw harvest, and the drain's re-offer is unchanged: every non-ok terminal with `retry` budget is re-offered, now lessons-fed.

## Why
Section 11.3: the recovery sandwich has exactly one model judgment, asked one question (what should happen next?) over a closed verdict vocabulary, with the deterministic layer refusing to ask when asking is pointless (section 2). Section 11.2 fixes the handler order harvest -> dispatch -> journal -> wipe and puts the diagnosis draw BEFORE the terminal write so the terminal carries the recovery's own cap state. After `spine-harvest` the handler is harvest -> infra draw -> journal -> wipe: a re-offer repeats the failure with only the raw prior findings, and every render of a lineage carries every raw harvest, which is exactly the accretion section 11.2 bounds by swapping a diagnosed attempt's payload for its typed lessons. The deterministic routing (the escalation ladder, the Reject queue, section 11.4) is the next seed batch; it routes on the verdict this ticket records, so the record shape is the contract. Pre-ladder the drain keeps the Phase 1 re-offer for every verdict and every `call`: section 11.4 auto-resolves a Reject arrival with `retry` budget to `keep` (one findings-fed re-entry, one unit drawn) and pre-queue the stem just terminals non-ok, so a re-offer that now carries the verdict and lessons is that re-entry, not a silent retry; a verdict-keyed park would be a hold whose only release is a ticket change, landing before anything machine-produces one (section 2), and the bootstrap drain runs headless (section 11.4).

## Scope in
A new module `squatch/diagnose.py` owning: `VERDICTS`, the closed verdict vocabulary `retry | escalate | split | reject | abandon-human`; `DiagnosisInput` (an `Artifact`: `stem`, the ticket text, the attempt's `harvest.json` text, the run record text or null, the committed branch diff `base...<stem>` read through the existing `Git.diff` and cut to `DIAG_DIFF_CHARS` = 20000 characters, and the prior attempts' journaled lessons); `Diagnosis` (an `Artifact` the model emits: `verdict` in `VERDICTS`, `lessons` -- a non-empty tuple of short strings, each at most 300 characters, written for the next implementer -- and `reason`, one line); `DiagnosisRecord`, the closed record that rides the terminal body under key `diagnosis` and is the whole content of `tickets/<stem>/diagnosis.json`: `run_seq`, `outcome` (the diagnosed terminal), `call` in the closed set `ok | synthetic | skipped | invalid_artifact | infra_error | timeout`, `verdict` (a `VERDICTS` value or null), `lessons`, `reason` (null unless `call` is `ok` or `synthetic`), `detail` (the verbatim skip reason, or the call's own terminal reason, else null); a pure stage builder `diagnose_stage(spec, *, tier, effort)` returning the `LLMStage` (name and surface `diagnose`, consumes `DiagnosisInput`, emits `Diagnosis`, no gates) that renders the spec's slots as data blocks -- importable with no journal, config, or git, because the eval harness of the next seed drives it; and `Diagnoser`, the one entry point the terminal handler calls, which decides in this fixed order: (1) a `premise_failed` or `budget_exceeded` terminal is never diagnosed -- `call: skipped`, `detail` naming the rule (the premise park is released by a ticket change, section 18; the exhausted ceiling blocks the call itself, section 11.3) -- no draw, no call; (2) `caps.spent(config, events, stem)` from `squatch/caps.py` non-null -- `call: skipped`, `detail` the spent reason verbatim, no draw, no call (section 11.1: caps fire first); (3) the run's worktree missing on disk -- the synthetic short-circuit: `call: synthetic`, `verdict: abandon-human`, one lesson naming the missing workspace, no draw, no call; (4) otherwise ONE `diagnosis` unit is drawn through the `cap_consumed` writer of `squatch/caps.py` (body `cap: diagnosis`, `ticket_sha`, `run_seq`) BEFORE the call, then the call runs through a `Driver` the `Diagnoser` owns over the SAME `LLMEffect`, `Spool`, and `EngineLog` the stages use (so the ticket's stuck budget already set on the effect bounds it, the effect key is `llm/<stem>/<run_seq>/diagnose/<run_seq>/<call_seq>`, and the spool and engine log are the ones the operator already reads) with `retry_cap=DIAGNOSE_RETRY_CAP` = 1 -- a verdict outside the vocabulary or a malformed reply is the driver's bounded re-prompt (section 5 invariant 2) and, still invalid, `call: invalid_artifact` with `verdict: null` (fail-closed, section 11.3); the call's own `infra_error` or `timeout` records `call` accordingly with `detail` the driver's reason and draws nothing further. `specs/diagnose.md`: the `diagnose` prompt spec (section 8) with `llm_surface: diagnose`, `consumes: DiagnosisInput`, `emits: Diagnosis`, `gates: []`, `version: "1.0"`, tier and effort `medium` (the stage runs at the TICKET'S `agent_tier`/`agent_effort`, section 6), the five fixed prose sections, and slots `ticket` (origin host), `harvest` (untrusted), `run_record` (untrusted, optional), `diff` (untrusted, optional), `prior_lessons` (untrusted, optional); its Task states each verdict's meaning from section 11.3-11.4 -- `retry`: a fixable oversight the findings now steer, re-run at the same capability; `escalate`: more capability would help, the model never names a tier or effort; `split`: the ticket is too large for one attempt; `reject`: the ticket as written cannot be satisfied, the run proved it; `abandon-human`: an environment, credential, or workspace failure no retry or capability fixes -- and its Output format is one JSON object with exactly the `Diagnosis` fields. `squatch/artifacts.py` gains `SUBSTEP_NAMES = frozenset({"diagnose"})` beside `STAGE_NAMES`, `StageName` unchanged (section 5 invariant 6: `diagnose` is a substep, never a Stage), and `LLMStage.__post_init__` in `squatch/driver.py` admits a name in `STAGE_NAMES | SUBSTEP_NAMES`. The stage-dispatch seam gains the diagnosis: the `Pipeline` protocol in `squatch/runner.py` gains `diagnose(ticket, delivery, *, run_seq) -> DiagnosisRecord`, the production `Pipeline` in `squatch/merge.py` implements it by delegating to a `Diagnoser` that `compose_pipeline` builds over the same composed stages, and every test pipeline fake (`tests/test_cli.py`, `tests/test_drain.py`, `tests/test_drain_upgrade.py`, `tests/test_terminal.py`, `tests/test_reconcile.py`) implements it. `squatch/runner.py`'s terminal handler for every non-ok outcome runs, in order: harvest (as landed), the `infra` draw where it applies (as landed -- so the diagnosis pre-check reads the cap state this terminal itself moved), the diagnosis through the seam, the lift of `diagnosis.json` into the canonical ticket dir through the ONE lift path in `squatch/stages.py` (its own ticket-plane commit kind `diagnosis`, every terminal -- skipped and synthetic records included), then the terminal `state_transition` whose body gains `diagnosis` = the record, then the wipe. `Stages._prior_attempts` in `squatch/stages.py` swaps the render per attempt: an earlier attempt whose journaled terminal carries a `diagnosis` with a non-null `verdict` renders one line with its terminal reason and verdict plus one line per lesson, and NONE of that attempt's raw harvest lines, run record, or spool tails; an attempt with no journaled verdict renders raw exactly as `spine-harvest` landed it; the senior `review.md`/`checks.json` fold and the criteria-position contract are unchanged. `squatch/drain.py`'s eligibility, park, and re-offer rules are unchanged: every non-ok terminal with `retry` budget is re-offered with one `retry` draw whatever its `diagnosis` verdict or `call` (pre-ladder, `escalate` re-runs at the authored capability because the pre-ladder tier rule already runs every seed at HIGH; `split`, `reject`, `abandon-human`, and a non-`ok` call are the section 11.4 auto-`keep` re-entry until the ladder/Reject-queue seed routes on them), the only parks stay the ones the plan already sanctions (a spent spine cap, `premise_failed`, the over-bound refusal), and the re-offer report line gains the verdict and its lessons when the latest terminal carries a `diagnosis`; the verdict and `call` ride the terminal body verbatim so the next batch's ladder and Reject-queue seeds route on the record, never on a drain rule this ticket adds. Tests for every rule above; `tests/test_drain_reentry.py` carries the engine's data-block delimiter and so cannot be a `Context` file: read it in the worktree before extending it, and read `squatch/caps.py` and `squatch/harvest.py` there too (they land with the `depends` and did not exist when this seed was authored). Read `squatch/llm.py`, `squatch/llmeffect.py`, `squatch/effects.py`, and `squatch/config.py` there as well (kept out of `Context` so the base Implement render clears the section 8 bound with headroom).

## Scope out
No verdict-keyed park or eligibility rule in `squatch/drain.py` (a hold released only by a ticket change may not precede the machinery that produces one, section 2), no escalation ladder rung walk, no rung fold, no oscillation or identical-terminal short-circuit, no Reject queue, no `routed: reject_queue` marker, no `confirm`/`reject` verbs, no auto-keep, no `premise_bounce` draw (all the next batch, section 11.4). No spend ceiling and no `budget_exceeded` producer: the outcome's arm here only refuses the call. No drought exemption: no drought producer exists yet, so every `infra_error` and `timeout` that reaches the handler is diagnosed. No diagnosis on a reconcile `abandoned` reap (the stem re-enters eligibility on its own, section 18) and none on `premise_failed`. No Suggestion Box filing of lessons. No change to harvest's allowlist or its file set, to `ticket.md`, to `specs/implement.md`, or to `specs/review.md`; no routing row for `diagnose` in `config.yaml` (it inherits the `review` row, section 5); no new frontmatter field, config key, cap name, or journal event type. The diagnosis call's spool files share the attempt spool dir with the implement and review calls (the filed spool-collision item); harvest reads the spool before this call, so it is unaffected here.

## Scope fence
- squatch/diagnose.py
- specs/diagnose.md
- squatch/runner.py
- squatch/merge.py
- squatch/stages.py
- squatch/drain.py
- squatch/driver.py
- squatch/artifacts.py
- squatch/caps.py
- tests/test_diagnose.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_drain_reentry.py
- tests/test_driver.py
- tests/test_cli.py
- tests/test_drain_upgrade.py
- tests/test_reconcile.py

## Acceptance criteria
- In `tests/test_diagnose.py`, `specs/diagnose.md` loads through `load_spec` with surface `diagnose`, consumes `DiagnosisInput`, emits `Diagnosis`, and slots exactly `ticket`, `harvest`, `run_record`, `diff`, `prior_lessons` with the last three optional; `diagnose_stage` renders a `DiagnosisInput` with every slot inside a data block and renders one with a null run record and no prior lessons without those blocks.
- In `tests/test_diagnose.py`, `Diagnosis` accepts each of the five `VERDICTS` values and refuses a verdict outside them, an empty `lessons`, and a lesson over 300 characters; `DiagnosisRecord` refuses a `call` outside its closed set.
- In `tests/test_driver.py`, an `LLMStage` named `diagnose` constructs, `diagnose` is not in `STAGE_NAMES`, and a name outside `STAGE_NAMES | SUBSTEP_NAMES` still raises `ValueError`.
- In `tests/test_terminal.py`, a run ending `gate_failed` over a live worktree journals, in this order: the harvest lift commit, one `cap_consumed` with body `cap: diagnosis`, `ticket_sha` equal to the committed ticket blob sha, and the run's `run_seq`, the diagnose call's `effect_intent` and `effect_completion` under key `llm/<stem>/<run_seq>/diagnose/<run_seq>/1`, the `diagnosis` lift commit, then the terminal `state_transition` whose body `diagnosis` carries `call: ok` and the fake's verdict, lessons, and reason; `tickets/<stem>/diagnosis.json` on main parses to that same record; and after `Runner.dispatch` returns the worktree directory is gone.
- In `tests/test_terminal.py`, the diagnose call's recorded request carries the attempt's `harvest.json` text and the ticket text inside data blocks, and its `diff` block is at most `DIAG_DIFF_CHARS` characters long for a branch diff longer than that.
- In `tests/test_terminal.py`, a run ending `infra_error` journals its `infra` draw before its `diagnosis` draw and both before the terminal; under config `caps: {infra: 1}` a run ending `infra_error` journals no `diagnosis` draw and no diagnose effect, and its terminal's `diagnosis` carries `call: skipped` with `detail` exactly `infra cap spent (1 of 1 drawn)`.
- In `tests/test_terminal.py`, a run whose workspace never materialized journals `diagnosis` with `call: synthetic` and `verdict: abandon-human`, no `cap_consumed` naming `diagnosis`, and no diagnose effect; a `premise_failed` terminal journals `call: skipped` with no draw and no diagnose effect; both still lift `tickets/<stem>/diagnosis.json`.
- In `tests/test_terminal.py`, a diagnose reply outside the vocabulary is re-prompted exactly once (two diagnose effect keys, call_seq 1 and 2) and, still invalid, the terminal's `diagnosis` carries `call: invalid_artifact` with `verdict: null`, and exactly one `diagnosis` draw was journaled.
- In `tests/test_drain_reentry.py`, the second attempt's Implement prompt carries, inside the `prior_attempts` block, the first attempt's terminal reason and each of its journaled lessons verbatim and does not carry that attempt's harvest `diff --stat` line or any spool tail; a prior attempt whose terminal carries no `diagnosis` verdict still renders its raw harvest lines; the first attempt still renders no `prior_attempts` block.
- In `tests/test_drain.py`, a stem whose latest terminal's diagnosis verdict is `retry` is re-offered with one `retry` draw, and one whose verdict is `escalate` likewise; a stem whose latest verdict is `reject`, `split`, or `abandon-human`, or whose `call` is `invalid_artifact`, with `retry` budget remaining is re-offered with one `retry` draw, its re-offer line contains the verdict and every lesson, and its journaled terminal body carries that verdict and `call` verbatim; a stem whose `retry` cap is spent stays parked exactly as in Phase 1 whatever its verdict; a stem whose latest terminal has no `diagnosis` key is re-offered as in Phase 1.
- In `tests/test_cli.py`, `FakePipeline` implements `diagnose`, and every Phase 1 and batch 1 claim in `tests/test_cli.py`, `tests/test_drain.py`, `tests/test_drain_upgrade.py`, `tests/test_terminal.py`, and `tests/test_reconcile.py` still passes.
- `grep -rn "VERDICTS = " squatch` reports exactly one definition, in `squatch/diagnose.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_diagnose.py -q
uv run pytest tests/test_terminal.py tests/test_drain.py tests/test_drain_reentry.py tests/test_driver.py tests/test_cli.py tests/test_drain_upgrade.py tests/test_reconcile.py -q
grep -rn "VERDICTS = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the diagnosis cannot sit in `squatch/runner.py`'s handler between the harvest and the terminal write without a second terminal writer or a second lift path, if `diagnose` cannot be admitted as an `LLMStage` name without adding it to `StageName`, if the `spine-harvest` terminal body or `squatch/caps.py` writer as landed cannot carry this record without changing their shape, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
