---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 names the requisition_review unit KNOWN-HARD for coupling, so its
# three chained seeds start high/high; the citing evidence is plan section 19.
agent_tier: high
agent_effort: high
---
## Depends on
- requisition-review-call

## Context
- squatch/driver.py
- squatch/gates.py
- squatch/tickets.py
- squatch/config.py
- squatch/artifacts.py
- tests/test_gates.py
- tests/test_driver.py

## Plan contract
- section 7
- section 11
- section 13
- section 19

## Goal
The Author path consumes `requisition_review`: an authored box ticket is feasibility-reviewed inside the Author driver loop before it commits, a `snag` re-prompts the Author within the driver's local allowance with the review findings in criteria position, an `rma` or an exhausted allowance ends the authoring pass with the message left `pending` carrying the verdict and no ticket committed, and an `approve` commits exactly as `author-stage` landed it.

## Why
Section 7 runs `requisition_review` at AUTHORING for every machine-authored ticket whatever its starting state -- a draft-starting box ticket carries the verdict on its draft, and the later human `confirm` flip re-runs nothing -- so the gate belongs in the Author stage's own gate list beside `ticket_schema`, where section 5 invariant 2 already routes a hard finding back into the bounded re-prompt. Section 11.1 sizes that loop: an authoring-time re-prompt has no lineage, so the DRIVER'S local allowance from `caps.retry` bounds it, and exhaustion terminates the pass with the cap named. Section 13 fixes the verdict semantics: a `snag` re-authors within caps, an `rma` -- a plan defect the author cannot fix -- parks for a human, which on the box path means the message rests `pending` with the finding for the operator's next `squatch triage`. Section 19 makes this the second of the three chained deliverables: the call landed with no consumer, this seed wires the box path and nothing else, and the seed path is the next seed, each fencing the module that owns its seam.

## Scope in
`squatch/author.py`: `author_stage` gains `RequisitionGate` after `TicketSchemaGate` in its gate tuple, constructed over a resolver that yields the one `(stem, ticket text)` target of the emitted `AuthoredTicket`, reviewed at that ticket's authored `agent_tier`/`agent_effort`; the driver's gate loop feeds every `requisition_review` finding back as a re-prompt finding exactly as it feeds `ticket_schema` ones, so a `snag` re-prompts the Author with the findings in the driver's findings block; the driver runs the grammar gate first and the review only when grammar passes (a review of an ungrammatical ticket is a wasted call); an `rma` finding is terminal for the pass -- `Author` recognizes the `rma` road on the failing finding, makes no further call, leaves the message `pending` with the verdict summary and findings recorded additively on the message's `triage` field through `squatch/box.py`, and reports the road `fix the plan (or the message) and re-run squatch triage`; an allowance exhausted on repeated `snag` verdicts leaves the message `pending` the same way naming the retry allowance; an `approve` commits through `Intake.commit` and resolves the message `authored` exactly as landed. `specs/author.md` gains `requisition_review` in its `gates` list and one On-failure sentence directing the model to answer the review findings by re-authoring, never by arguing. `squatch/driver.py` is fenced per the section 19 ownership law as the gate loop's owner; it changes only if its gate loop cannot run an async gate that makes its own driver call. Tests for every rule above; read `squatch/author.py`, `squatch/requisition.py`, `tests/test_author.py`, and `tests/test_requisition.py` in the worktree (they land with the `depends`).

Driver-hook correction: the final sentence above is superseded for one explicit need. `squatch/driver.py` may add a minimal generic `terminal_findings` predicate applied to the complete `run_gates` result; it returns the gate failure immediately for requisition-review `rma` without per-gate short-circuiting and without losing findings from any gate. No other driver behavior changes. The Author resolver uses the same complete ticket-schema predicate as `TicketSchemaGate`, including `RESERVED_STEMS`, before invoking review.

## Scope out
No seed-path wiring: the Check stage and the merge admission do not run the review here (the next seed). No human-intake advisory run. No change to the verdict vocabulary, the spec's slots, the effect key domain, `squatch/policy.py`, the starting-state rule, `squatch/triage.py`'s pass shape, or any frontmatter field, config key, cap, or journal event type.

## Scope fence
- squatch/author.py
- specs/author.md
- squatch/driver.py
- tests/test_author.py
- tests/test_triage.py
- tests/test_driver.py
- tests/test_specs.py

## Acceptance criteria
- In `tests/test_author.py`, `author_stage` carries gates `ticket_schema` then `requisition_review`, and `specs/author.md` loads with that gate list.
- In `tests/test_author.py`, under a `FakeLLM` scripted with a valid ticket, then a `requisition_review` `snag`, then a valid ticket, then an `approve`, `Author` makes exactly four calls -- two under `llm/author/<id>/0/` and two under `llm/requisition_review/<stem>/` -- the second Author request carries the snag finding inside the findings block, and the ticket commits `source: box:suggestion` with the message `authored`.
- In `tests/test_author.py`, a ticket scripted grammar-invalid is re-prompted on `ticket_schema` with no `requisition_review` call made for that attempt.
- In `tests/test_author.py`, an otherwise valid ticket using a reserved stem is likewise re-prompted on `ticket_schema` with no `requisition_review` call; the resolver and `TicketSchemaGate` cannot drift on grammar admission.
- In `tests/test_author.py`, a review scripted `rma` ends the pass after that one review call, leaves no `tickets/<stem>/` dir, leaves the message `pending` with the `rma` summary and findings on its `triage` field, and the report names `squatch triage`.
- In `tests/test_author.py`, under config `caps: {retry: 1, diagnosis: 1}` a review scripted `snag` twice leaves the message `pending`, no ticket dir, and the report naming the retry allowance.
- In `tests/test_driver.py`, every Phase 0-1 driver claim still passes with an async gate that performs its own driver call inside the gate loop; the additive `terminal_findings` hook stops only after the complete gate set has run and preserves all findings.
- In `tests/test_triage.py`, every existing pass scenario that reaches Author scripts and observes the mandatory `requisition_review` call; an exhausted fake can never be treated as approval, and the commit-failure continuation case still reaches its later item after review.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_author.py -q
uv run pytest tests/test_driver.py tests/test_specs.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the driver's gate loop as landed cannot host a gate that itself calls the driver without a change outside `squatch/driver.py`, if the `RequisitionGate` as landed cannot be constructed over the Author's single target, if the message's `triage` field as `box-triage` landed it cannot carry the verdict additively, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
