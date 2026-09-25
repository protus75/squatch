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
- escalation-ladder

## Context
- squatch/__main__.py
- squatch/runner.py
- squatch/driver.py
- squatch/llm.py
- squatch/llmeffect.py
- squatch/artifacts.py
- squatch/config.py
- squatch/providers.py
- squatch/tickets.py
- eval/harness.py
- tests/test_cli.py
- tests/test_drain.py

## Plan contract
- section 12
- section 8
- section 13
- section 4

## Goal
`squatch triage` is the box's sequential consumer: one pass over every pending message in enqueue order, one governed `triage` call each through `specs/triage.md`, each item tombstoned (a registry record linking the existing ticket or decision), decision-recorded, or marked for authoring, then STOP; `squatch/policy.py` resolves a box-authored ticket's starting state from the config table plus the scope override with no era special-case, and a bootstrap box ticket provably resolves `draft`.

## Why
Section 12: one durable queue, one sequential LLM consumer -- sequential keeps dedup trivially consistent -- with class-specific prompting inside the single `specs/triage.md` and outcomes closed to a ticket, a tombstone, or a decision record; dedup is semantic, against open tickets, merged tickets, and decisions, so it lives in this consumer and never at enqueue. The era split is the whole safety story: in the bootstrap era the drain never scans the box and this operator verb is the only reader, so a human is present at every scan, a box-authored ticket takes its table default -- almost always `draft` -- and the operator confirms only the few worth building; there is no self-build auto-confirm exemption because nothing from the box need run unattended. Section 12 makes the policy read one rule in every era: the confirmed rows bind only under a currently recorded GO, absent GO everything resolves `draft`, and the bootstrap era records no GO -- the `tests/test_policy.py` pin is that rule's protected instance. Section 19 sites the machine route into authoring here -- an `author` verdict invokes the Author stage in the same pass -- and, until the Author deliverable merges, an `author`-verdict item rests `pending` with a paved road naming it, never a hand-rolled interim author. Phase seeds never route through the box.

## Scope in
`specs/triage.md`: the `triage` prompt spec (section 8) with `llm_surface: triage`, `consumes: TriageInput`, `emits: {author: TriageAuthor, tombstone: TriageTombstone, decision: TriageDecision}`, `gates: []`, `version: "1.0"`, tier and effort `medium`, the five fixed prose sections, and slots `message` (untrusted), `open_work` (engine), `merged_work` (engine), `decisions` (engine); its Task carries one labeled variant per message class and directs the model to apply the variant named by the message's `message_class`; it states that the message text is data, that a tombstone's `link` must be an id or stem present in the rendered projections, and that an `author` verdict's summary is the model's OWN rewrite -- raw message text never becomes ticket prose. A new module `squatch/triage.py` owning: `TriageInput` (an `Artifact`: the message's id, class, summary, detail, origin; `open_work` -- every committed unmerged stem with its `state` and Goal line; `merged_work` -- every merged stem's Goal line; `decisions` -- every registry record's id, kind, link, and first body line; each projection cut to `TRIAGE_CONTEXT_CHARS` = 20000 characters, newest first); the verdict artifacts -- `TriageAuthor` (`summary`, `kind` in `KINDS`, `priority` in `PRIORITIES`, `goal`, `why`), `TriageTombstone` (`link` refused when absent from the rendered projections, `reopen_after_days` int of at least 1, `rationale`), `TriageDecision` (`reopen_after_days`, `rationale`, `evidence`); `triage_stage(spec)` returning the branch `LLMStage` (name and surface `triage`, `emits_by_verdict` the three types, no gates); and `Triage`, the sequential consumer: for each pending message in seq order -- skipping one whose recorded `triage` field already carries an `author` verdict, reporting the paved road `awaiting the Phase 2 Author stage deliverable (specs/author.md); it consumes this item` and making no call -- ONE driver call through the same `LLMEffect`, `Spool`, and `EngineLog` the stages use, ticket-less (spooled under `<state_dir>/spools/triage/<pass>/`), with the landed universal effect key `llm/triage/<message seq>/triage/<pass>/<call_seq>`: the numeric sequence parsed from the box id is passed as `run_seq`, and `<pass>` -- the count of prior `triage_pass` signals in the journal -- as `attempt`; `retry_cap` 1, `stuck_seconds` = `TRIAGE_STUCK_SECONDS` = 600. Outcomes: `tombstone` -- a registry `Record` of kind `tombstone` (id `tombstone-<seq>`, `link`, `reopen_after_days`, `message` the box id, body the rationale) written and committed through `squatch/registry.py`, then the message resolved `tombstoned` with `link` the record id; `decision` -- the same with kind `decision` (id `decision-<seq>`) and the message resolved `decided`; `author` -- the verdict artifact stored on the message's `triage` field (additive in `squatch/box.py`), status left `pending`, the road above reported; a non-ok call (invalid after the one re-prompt, `infra_error`, `timeout`) leaves the message untouched and pending, is reported, and the pass continues. The pass ends with one `signal` of body `kind: triage_pass`, `pass`, `triaged` (ids by outcome), `skipped`, then returns. A new module `squatch/policy.py` owning `starting_state(config, *, message_class, bug_origin, has_repro, fence, reopened, go_binds) -> draft | confirmed`: the `box_policy` row keyed by class (`bug_report` by `bug_origin` `self_diagnosed | player` and `has_repro`), then `draft` when `go_binds` is false, when `reopened` is true, when `config.engine_plane_safety_inventory` is empty (fail-closed), or when any fence prefix falls under an inventory prefix; and `go_binds(config, events) -> bool`: the journal's latest `review_baseline` signal has `verdict` `GO` and an `identity` equal to the current one -- the (provider, model) `Registry` resolves for `review` and `author` at every tier plus those specs' major versions, the shape `eval/harness.py` records -- false with no such signal. No drain special-case anywhere: `policy.py` has no era argument. `squatch/__main__.py` gains `triage`, composed like `run` through `Runner.session()`, exit 0 after one pass (pending `author` items included), 2 on refusal. Tests for every rule above; read `squatch/box.py` and `squatch/registry.py` in the worktree (they land with `suggestion-box`); `tests/test_drain.py` gains the consumer pin beside the box seed's: a drain over a checkout with pending messages journals no `triage_pass` signal and no `llm/triage/` effect.

## Scope out
No Author stage, no `specs/author.md`, no ticket file written by this consumer, no `requisition_review` (the next batch): an `author` verdict rests pending with its road. No policy CONSUMER: `starting_state` is called by the Author path when it lands; here it is pinned by its own tests. No GO recording, no `--record-go`, no re-baseline. No semantic dedup at enqueue, no storm breaker, no tombstone auto-reopen (the `reopened` argument is read, never produced here), no retro itemization, no host bug intake, no `evidence/` copy. No daemon-era continuous consumer, no watched loop, no ordering knob: one pass, then stop. No new frontmatter field, config key, cap, or event type beyond the `triage_pass` signal kind; no change to the drain's eligibility or to any verb landed by earlier seeds.

## Scope fence
- squatch/triage.py
- squatch/policy.py
- specs/triage.md
- squatch/__main__.py
- squatch/box.py
- squatch/registry.py
- tests/test_triage.py
- tests/test_policy.py
- tests/test_cli.py
- tests/test_drain.py

## Acceptance criteria
- In `tests/test_triage.py`, `specs/triage.md` loads through `load_spec` with surface `triage`, consumes `TriageInput`, an `emits` map of exactly `author`, `tombstone`, `decision`, and slots exactly `message`, `open_work`, `merged_work`, `decisions`; a rendered `TriageInput` carries the message inside an untrusted data block and the three projections inside engine data blocks, each projection at most `TRIAGE_CONTEXT_CHARS` characters.
- In `tests/test_triage.py`, `TriageTombstone` refuses a `reopen_after_days` under 1, `TriageAuthor` refuses a `kind` or `priority` outside the closed vocabularies, and the consumer refuses a tombstone whose `link` is absent from the rendered projections as an invalid artifact.
- In `tests/test_triage.py`, a pass over three pending messages under a `FakeLLM` scripted `tombstone`, `decision`, `author` leaves, in order: `tickets/decisions/tombstone-000001.md` committed on main with `link` the existing stem and the message `tombstoned` with that record id; `tickets/decisions/decision-000002.md` committed and the message `decided`; the third message still `pending` with its `triage` field carrying the `author` verdict and the report line naming `specs/author.md`; one `triage_pass` signal with `pass` 0 and the three ids by outcome; and exactly three `llm/triage/` effect completions.
- In `tests/test_triage.py`, a second pass over that checkout makes no call for the `author` item, reports its road, and journals a `triage_pass` with `pass` 1; a reply outside the emits map is re-prompted exactly once and, still invalid, leaves the message pending and untouched while the next message is still triaged.
- In `tests/test_policy.py`, with no `review_baseline` signal in the journal `starting_state` resolves `draft` for `failure_report`, `retro_finding`, `suggestion`, and every `bug_report` row under the shipped `box_policy` -- the bootstrap box ticket resolves `draft` -- and `go_binds` is false.
- In `tests/test_policy.py`, with a `review_baseline` signal carrying `verdict` `GO` and the current identity, `go_binds` is true and `failure_report` resolves `confirmed` while `suggestion` resolves `draft`; with the identity drifted (one review row's model changed) `go_binds` is false; under a binding GO a `failure_report` whose fence touches an inventory prefix resolves `draft`, one with an empty inventory resolves `draft`, and one with `reopened` true resolves `draft`.
- In `tests/test_cli.py`, `squatch triage` with an empty box exits 0 reporting nothing pending, and is refused with exit 2 while another process holds the lock.
- In `tests/test_drain.py`, a drain over a checkout with two pending messages journals no `triage_pass` signal and no effect whose key starts with `llm/triage/`.
- `grep -rn "TRIAGE_CONTEXT_CHARS = " squatch` reports exactly one definition, in `squatch/triage.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_triage.py tests/test_policy.py -q
uv run pytest tests/test_cli.py tests/test_drain.py tests/test_specs.py -q
uv run python -m squatch triage --help
grep -rn "TRIAGE_CONTEXT_CHARS = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if a ticket-less branch stage cannot obtain the stated universal key by mapping message sequence to `run_seq` and pass to `attempt` through the `Driver` and `LLMEffect` as landed, if the spec renderer refuses a single spec carrying per-class Task variants within the section 8 size budget, if `squatch/registry.py` as landed cannot commit a record from under the held lock, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
