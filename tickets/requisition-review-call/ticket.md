---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 names the requisition_review unit KNOWN-HARD for coupling (it
# proved unbuildable as one ticket in both prior builds), so its three chained
# seeds start high/high; the citing evidence is plan section 19, cited below.
agent_tier: high
agent_effort: high
---
## Depends on
- author-stage

## Context
- squatch/stages.py
- squatch/driver.py
- squatch/llm.py
- squatch/llmeffect.py
- squatch/gates.py
- squatch/artifacts.py
- squatch/merge.py
- tests/test_merge.py

## Plan contract
- section 7
- section 9
- section 19
- section 8
- section 13

## Goal
The pure `requisition_review` call exists with no consumer: `squatch/requisition.py` renders ONE authored ticket per review pass through `specs/requisition_review.md` -- its own text, its `Context` closure, its cited plan sections, the ticket plane, and a mechanical render-feasibility measurement -- and returns a closed `approve | snag | rma` verdict with `requisition_review` findings; a `RequisitionGate` wraps that call in the section 5 Gate protocol under the existing `requisition_review` gate code; and the merge admission provably never runs it.

## Why
Section 7 names two engine review surfaces, and `requisition_review` is the feasibility review that stands to an authored ticket as code review stands to a diff: it judges a ticket BUILDABLE against the shipped engine and the plan it renders -- a criterion contradicting merged behavior, a fence missing a file the criteria force, mutually unsatisfiable criteria, an over-bound base render, an exit read with no emitter. Section 19 makes the unit three chained deliverables because it proved unbuildable as one: this seed is the call, the spec, and the gate registration, and NOTHING calls it yet, so its tests drive it directly and its two consumers wire it in their own reviewed diffs. Section 9 fixes the render bound: the material is PER AUTHORED SEED -- one render each, its own text and Context closure -- never a union over a batch or the plane's history, so the per-seed prompt stays under the section 8 bound. Section 19 fixes render feasibility as MECHANICAL: the base Implement render measured at the ladder-top effort's bound with declared headroom, before the ticket commits, so an over-bound ticket is a `snag` at authoring, never a park at run time. The merge-time law of section 9 puts this surface at authoring only; the merge admission's re-run set is the mechanical codes, so a test pins that admission never journals a `requisition_review` call.

## Scope in
`specs/requisition_review.md`: the prompt spec (section 8) with `llm_surface: requisition_review`, `consumes: RequisitionInput`, `emits: {approve: RequisitionApprove, snag: RequisitionSnag, rma: RequisitionRMA}`, `gates: []`, `version: "1.0"`, tier and effort `high` (the call resolves at the REVIEWED ticket's `agent_tier`, section 6; with no `requisition_review` routing row it inherits the `review` row, section 5), the five fixed prose sections, and slots `ticket` (host), `context_files` (host), `plan_sections` (engine), `plane` (engine), `render_measure` (engine), `fence_facts` (engine); its Task directs the reviewer through the section 7, 9, and 19 duties in this order: the fence CLOSURE -- trace the reference closure of every symbol the scope-in changes and the recorded-value closure of every constant it bumps, and name every forced file the fence omits, every fence entry naming an existing file that `Context` omits, and every existing test the criteria's behavior flip contradicts; contradiction with merged behavior the rendered Context shows; mutual satisfiability of the criteria; the section 9 ownership law (a hooked seam's owning module is fenced); the D10 seed-grant bar (a seed realizes exactly what its cited plan sections state); and, for a ticket whose fence covers the tickets plane or whose criteria read committed artifacts, EXIT-READ CLOSURE -- every read names an emitter among merged or seeded deliverables, and a committed-report read names both its machinery and its producer. Verdicts: `approve` (no finding), `snag` (fixable at authoring: re-author within caps), `rma` (a plan defect the author cannot fix: park for a human). Output format is one JSON object with `verdict`, `summary`, and `findings` each `{code: requisition_review, path, line, message, paved_road}`. A new module `squatch/requisition.py` owning: `RequisitionInput` (an `Artifact`: the stem; the ticket text; `context_files` -- each `Context` path's contents, each cut to `REQ_FILE_CHARS` = 12000; `plan_sections` -- the `Plan contract` ids resolved through `resolve_plan_sections`; `plane` -- committed unmerged stems with `state` and Goal line plus merged stems' Goal lines, cut to `REQ_PLANE_CHARS` = 20000; `render_measure`; `fence_facts` -- per fence entry, whether it exists on main); `RenderMeasure` (`chars`, `bound`, `headroom`, `over`): the ticket's base Implement render -- standing inputs, zero attempt history, produced by a new pure `Stages.render_implement(ticket, *, effort)` in `squatch/stages.py` that the production `_implement` render closure also uses (one render path) -- measured at effort `max`, `over` when `chars` exceeds `bound * REQ_RENDER_HEADROOM` with `REQ_RENDER_HEADROOM` = 0.75; the three verdict artifacts (`findings` empty exactly for `approve`, non-empty otherwise, every finding `code` `requisition_review`); `requisition_stage(spec, *, tier, effort)` returning the branch `LLMStage` (name and surface `requisition_review`, `emits_by_verdict` the three types, no gates); and `RequisitionReview.review(stem, text, *, run_seq, call_seq_base) -> Verdict`: builds the input, and when `render_measure.over` returns a mechanical `snag` naming the chars, the bound, and the road `shrink the inputs or split the ticket` WITHOUT a model call; otherwise ONE driver call through the same `LLMEffect`, `Spool`, and `EngineLog` the stages use, at the reviewed ticket's `agent_tier`/`agent_effort`, effect key `llm/requisition_review/<stem>/<blob sha12 of the text>/<call_seq>` (a re-run over unchanged text replays the recorded verdict, section 6), `retry_cap` = `REQ_RETRY_CAP` = 1 -- a verdict outside the vocabulary re-prompts once and, still invalid, is `rma` with a finding naming the invalid reply (fail-closed, section 11.3); the call's own `infra_error` or `timeout` is likewise a fail-closed `rma` naming the reason. `RequisitionGate` (code `requisition_review`, a paved road, async `check(artifact, workspace)`), constructed over a target resolver its consumer supplies (`targets(artifact, workspace) -> Sequence[(stem, text)]`), reviews each target with ONE render per target and returns `fail` with every non-approve finding (an `rma` finding's paved road names the plan-defect road) and `pass` with no targets or all approved; `gate_lint` accepts it. `squatch/artifacts.py` needs no change: `requisition_review` is already a gate code and an `llm_surface`. Tests for every rule above, all offline under `FakeLLM`; `tests/test_merge.py` gains the merge-time pin: a full admission journals no effect whose key starts with `llm/requisition_review/`. Read `squatch/specs.py` (the render bound and `RenderRefused`) in the worktree: it carries the engine data-block delimiter, which the render contract refuses as Context; read `squatch/tickets.py`, `squatch/config.py`, `squatch/providers.py`, `squatch/git.py`, and `tests/test_gates.py` there too (kept out of `Context` so the base Implement render clears the section 8 bound with headroom).

## Scope out
No consumer: nothing in `squatch/author.py`, `squatch/triage.py`, the Check stage, or the merge admission calls the review or the gate (the next two seeds). No mechanical fence-closure analyzer (the closure is the reviewer's judgment under the prompt; the mechanical check is a D10 return, section 9 -- the per-seed assertions of section 19 live in each seeding deliverable's own test file). No human-intake advisory run. No routing row for `requisition_review` in `config.yaml`. No change to `specs/implement.md` or `specs/review.md`, to `ticket.md`, to the drain, to any frontmatter field, config key, cap, or journal event type.

## Scope fence
- squatch/requisition.py
- specs/requisition_review.md
- squatch/stages.py
- tests/test_requisition.py
- tests/test_stages.py
- tests/test_merge.py
- tests/test_specs.py

## Acceptance criteria
- In `tests/test_requisition.py`, `specs/requisition_review.md` loads through `load_spec` with surface `requisition_review`, consumes `RequisitionInput`, an `emits` map of exactly `approve`, `snag`, `rma`, and slots exactly `ticket`, `context_files`, `plan_sections`, `plane`, `render_measure`, `fence_facts`; a rendered input carries the ticket text and each Context file inside host data blocks and the plan sections inside an engine data block.
- In `tests/test_requisition.py`, `RequisitionSnag` and `RequisitionRMA` refuse empty `findings`, `RequisitionApprove` refuses non-empty `findings`, and a finding with a `code` other than `requisition_review` is refused.
- In `tests/test_requisition.py`, over a fixture ticket whose base render fits the bound, `review` under a `FakeLLM` scripted `approve` makes exactly one call under key `llm/requisition_review/<stem>/<sha12>/1`, a second `review` of the same text makes no call and returns the recorded verdict, and a changed text takes a fresh key.
- In `tests/test_requisition.py`, a fixture ticket whose Context files push the base render past `REQ_RENDER_HEADROOM` times the `max`-effort bound returns a `snag` naming the chars and the bound with no call made; `REQ_RENDER_HEADROOM` equals 0.75.
- In `tests/test_requisition.py`, a reply outside the verdict vocabulary is re-prompted exactly once and, still invalid, returns `rma` with a finding naming the reply; a fake `infra_error` returns `rma` with the reason.
- In `tests/test_requisition.py`, `RequisitionGate` passes `gate_lint`, reports `pass` over a resolver yielding no targets without any call, `fail` carrying every finding when one of two targets is scripted `snag`, and `pass` when both are `approve`.
- In `tests/test_stages.py`, `Stages.render_implement` over a fixture ticket at effort `max` returns the same bytes the production Implement render sends on a first attempt, and the bound it is measured against shrinks from `medium` to `max`.
- In `tests/test_merge.py`, a full admission journals no effect whose key starts with `llm/requisition_review/`.
- `grep -rn "REQ_RENDER_HEADROOM = " squatch` reports exactly one definition, in `squatch/requisition.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_requisition.py -q
uv run pytest tests/test_stages.py tests/test_merge.py tests/test_specs.py -q
grep -rn "REQ_RENDER_HEADROOM = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the Implement render closure in `squatch/stages.py` cannot be exposed as a pure standing render without changing what the production first attempt sends, if a branch stage keyed on a blob sha cannot run through the `Driver` and `LLMEffect` as landed, if the render bound in `squatch/specs.py` cannot be measured at a chosen effort, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
