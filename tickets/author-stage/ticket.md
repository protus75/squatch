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
- box-triage

## Context
- squatch/tickets.py
- squatch/driver.py
- squatch/llm.py
- squatch/llmeffect.py
- squatch/artifacts.py
- squatch/gates.py
- squatch/config.py
- squatch/providers.py
- squatch/runner.py
- eval/harness.py
- tests/test_eval_harness.py
- tests/test_tickets.py
- tests/test_gates.py
- tests/test_cli.py

## Plan contract
- section 4
- section 5
- section 8
- section 12
- section 13
- section 11

## Goal
The Author stage exists and the triage consumer feeds it: an `author` verdict in a `squatch triage` pass invokes one governed `author` call through `specs/author.md`, the emitted ticket passes the grammar Requisition gate inside the driver's bounded re-prompt loop, commits to `tickets/<stem>/ticket.md` through the ONE ticket-plane lane with `source: box:<class>` and the starting state `squatch/policy.py` resolves, and the box message resolves `authored` linking the stem.

## Why
Section 4 names Author as the stage that consumes a triaged box message and emits the ticket, and section 12 makes the box consumer -> triage -> Author path the ONE machine route into authoring; Phase 1 deferred the stage because nothing executed it, and `box-triage` left an `author` verdict resting `pending` with a paved road naming this deliverable. Section 5 invariant 2 puts the grammar gate INSIDE the driver loop: a ticket that fails the section 13 grammar is fed back as findings and re-prompted within the driver's local allowance (section 11.1: an authoring-time re-prompt has no lineage to fold, so the allowance is sized from `caps.retry` and an exhausted allowance ends the pass with the cap named). Section 13 fixes who stamps what: the machine writes `source: box:<class>`, the policy table plus the scope override and the `gate_bypass` rule set the starting state, and every authoring path journals the same authoring-commit event the section 9 age term reads -- which is why the commit goes through `Intake.commit`, never a second lane. Section 8 keeps the message text data: the model writes its own prose, and raw report text never becomes ticket prose. Feasibility review (`requisition_review`) is the next seed; this stage lands the grammar-gated path it will wire into.

## Scope in
`specs/author.md`: the `author` prompt spec (section 8) with `llm_surface: author`, `consumes: AuthorInput`, `emits: AuthoredTicket`, `gates: [ticket_schema]`, `version: "1.0"`, tier and effort `medium` (the call is ticket-less and resolves at `routing_default_tier`, section 6), the five fixed prose sections, and slots `message` (untrusted), `triage` (engine), `ticket_contract` (engine: the resolved plan section 13 text), `plane` (engine), `tree` (engine), `context_files` (host, optional); its Task directs the model to write ONE complete `ticket.md` in the section 13 grammar -- `kind` and `priority` copied from the triage verdict, `agent_tier`/`agent_effort` `medium`/`medium` unless the ticket is known-hard, `Context` paths taken only from the rendered tree, a `## Scope fence` closed over every file the criteria force, no `state` and no `source` (the stage stamps them), the Goal and Why in the model's own words with the message text treated as data; its Output format is one JSON object with exactly the `AuthoredTicket` fields. A new module `squatch/author.py` owning: `AuthorInput` (an `Artifact`: the message id, class, summary, detail, origin; the `TriageAuthor` verdict; the plan section 13 text resolved through `resolve_plan_sections`; `plane` -- every committed unmerged stem with its `state` and Goal line plus every merged stem's Goal line, cut to `AUTHOR_PLANE_CHARS` = 20000; `tree` -- the repo's tracked file list from `git ls-files` through `squatch/git.py`, cut to `AUTHOR_TREE_CHARS` = 20000; `context_files` -- the contents of `config.context_files`); `AuthoredTicket` (an `Artifact` the model emits: `stem` matching the section 13 stem regex and `ticket`, the full file text); `author_stage(spec)` returning the `LLMStage` (name and surface `author`, consumes `AuthorInput`, emits `AuthoredTicket`, gates `(TicketSchemaGate,)`); and `Author`, the one entry point triage calls: ONE driver call through the same `LLMEffect`, `Spool`, and `EngineLog` the stages use, ticket-less (spooled under `<state_dir>/spools/author/<message id>/`), effect key `llm/author/<message id>/<pass>/<call_seq>` with `<pass>` the count of prior `triage_pass` signals, `retry_cap` = `config.caps.retry` (the driver's local per-invocation allowance, section 11.1), `stuck_seconds` = `AUTHOR_STUCK_SECONDS` = 900. `squatch/tickets.py` gains `TicketSchemaGate` (code `ticket_schema`, a paved road, async `check`) over an `AuthoredTicket`: `lint_ticket` with `resolve_stem` over the on-disk stems, plus a finding when the stem already exists on disk or is reserved -- every lint finding is the gate's finding, so the driver re-prompts on it. On an ok call: the starting state is `policy.starting_state(...)` over the message's class, `bug_origin`, `has_repro`, the ticket's fence, `reopened` false, and `policy.go_binds(config, events)`, forced to `draft` when the ticket carries any non-empty `gate_bypass` (section 12: the valve surfaces at the draft gate); `squatch/policy.py` gains that `bypass` argument. The text is written to `tickets/<stem>/ticket.md` through the filesystem seam and committed by `Intake.commit(stem, source="box:<class>", state=<state>)` -- the one lane, which lints again, pathspec-commits, and journals the `ticket_intake` signal (the age term); then the message resolves `authored` with `link` the stem through `squatch/box.py`. A non-ok call (invalid after the allowance, `infra_error`, `timeout`) or an exhausted allowance leaves the message `pending` with its `triage` verdict intact, reports the reason and the cap when spent, and the pass continues. `squatch/triage.py`: an `author` verdict invokes `Author` IN the same pass, for the item just triaged and for every pending item whose recorded `triage` field already carries an `author` verdict from an earlier pass (the road `box-triage` printed is retired); the `triage_pass` signal's `triaged` gains the authored stems under `authored`. Tests for every rule above; read `squatch/triage.py`, `squatch/policy.py`, `squatch/box.py`, and `tests/test_triage.py` in the worktree (they land with the `depends`), and `squatch/specs.py` there too (it carries the engine data-block delimiter, which the render contract refuses as Context).

Effect-key correction: the shorter key shorthand in the preceding paragraph is superseded by the landed universal seam. Pass the count of prior `triage_pass` signals as `run_seq` and the numeric box-message sequence as `attempt`, producing `llm/author/<pass>/author/<message seq>/<call_seq>` and `spools/author/<message seq>/`; `Driver` and `LLMEffect` remain unchanged.

## Scope out
No `requisition_review` call, no feasibility verdict, no `specs/requisition_review.md` (the next three seeds); the authored ticket passes grammar only, exactly the bootstrap floor of section 19. No human-intake change: `Intake.run` and its `source: human` stamping are untouched, and no advisory review runs at the front door. No new CLI verb, no daemon-era continuous consumer, no auto-confirm exemption, no GO recording. No dedup here: triage already deduplicated against open work, merged work, and decisions. No evidence copy, no host bug intake. No new frontmatter field, config key, cap, or journal event type: the authoring commit is the existing `ticket_intake` signal.

## Scope fence
- squatch/author.py
- specs/author.md
- squatch/tickets.py
- squatch/triage.py
- squatch/policy.py
- tests/test_author.py
- tests/test_tickets.py
- tests/test_triage.py
- tests/test_policy.py
- tests/test_specs.py
- tests/test_eval_harness.py

## Acceptance criteria
- In `tests/test_author.py`, `specs/author.md` loads through `load_spec` with surface `author`, consumes `AuthorInput`, emits `AuthoredTicket`, gates exactly `ticket_schema`, and slots exactly `message`, `triage`, `ticket_contract`, `plane`, `tree`, `context_files` with the last optional; a rendered `AuthorInput` carries the message inside an untrusted data block and the plan section 13 text inside an engine data block.
- In `tests/test_eval_harness.py`, the baseline signal now records Author spec major version `1` from the newly landed `specs/author.md` instead of the Phase 1 pre-Author null.
- In `tests/test_author.py`, `AuthoredTicket` refuses a `stem` outside the section 13 stem regex, and `TicketSchemaGate` fails an authored ticket missing `## Verification`, one whose stem already exists on disk, and one whose `Context` names a path that does not exist, each finding carrying a paved road.
- In `tests/test_author.py`, under a `FakeLLM` scripted first with a ticket missing `## Time budget` and then with a valid ticket, `Author` makes exactly two calls (keys `llm/author/<id>/0/1` and `llm/author/<id>/0/2`), the second request carries the first's `ticket_schema` finding, `tickets/<stem>/ticket.md` is committed on main with `source: box:suggestion` and `state: draft`, one `ticket_intake` signal names the stem with that source, and the message is `authored` with `link` the stem.
- In `tests/test_author.py`, under config `caps: {retry: 1, diagnosis: 1}` a fake that answers an invalid ticket twice leaves the message `pending` with its `author` verdict intact, no ticket dir on disk, and the report naming the retry allowance; a fake `Hang` past `AUTHOR_STUCK_SECONDS` is aborted and leaves the message `pending`.
- In `tests/test_author.py`, an authored ticket carrying a non-empty `gate_bypass` commits `state: draft` under a binding GO and a `failure_report` class, and `tests/test_policy.py` pins `starting_state(..., bypass=True)` as `draft` for every class.
- In `tests/test_triage.py`, a pass over one message scripted `author` followed by a valid ticket commits the ticket in the same pass, resolves the message `authored`, and journals a `triage_pass` whose `authored` names the stem; a second pass over a checkout holding a still-pending item with a recorded `author` verdict authors it without a second triage call.
- In `tests/test_specs.py`, `specs/author.md` lints under the shipped size budget beside the other specs.
- `grep -rn "AUTHOR_STUCK_SECONDS = " squatch` reports exactly one definition, in `squatch/author.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_author.py tests/test_triage.py tests/test_policy.py -q
uv run pytest tests/test_tickets.py tests/test_specs.py -q
grep -rn "AUTHOR_STUCK_SECONDS = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if a ticket-less authoring call cannot run through the `Driver` and `LLMEffect` as landed with a gate list inside the driver loop, if `Intake.commit` as `reject-verbs` factored it cannot commit a machine-sourced stem without a second lane, if `squatch/triage.py` as landed cannot invoke a second stage inside its pass, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
