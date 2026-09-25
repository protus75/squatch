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
- requisition-review-author

## Context
- squatch/stages.py
- squatch/merge.py
- squatch/tickets.py
- squatch/runner.py
- squatch/drain.py
- tests/test_merge.py
- tests/test_terminal.py

## Plan contract
- section 19
- section 9
- section 10
- section 13

## Goal
The seed path consumes `requisition_review`: a run whose worktree holds newly authored `tickets/<seed>/ticket.md` files is a seeding run, its own Check stage lints every seed, refuses a batch over `seeding.max_seeds_per_admission`, reviews each seed with one render, lifts an approved batch through the one ticket-plane lane as `confirmed` seeds with their authoring-commit signals, and the merge admission's MERGE-SAFETY tier refuses the seeding branch when any lifted seed lacks a recorded approval for the bytes now on main.

## Why
Section 19 sites the ONE seed-review point at the seeding ticket's own Check stage: a refused seed never commits, so no code-lane exception for `tickets/**` exists or is needed (section 10), and a grammar-valid but unbuildable seed never reaches the serial chain to park every downstream stem. Drain intake can only park a seed it already sees committed, which is why the review lives at Check and the PRE-ADMISSION seam is the last point that can refuse the seeding branch -- enforcing the same verdict, never a second judgment. Section 19's bounded-batch law makes batch size the blast radius of one rejected seed, so the cap is a hard finding; its RE-RUN rule makes a stem's own previously lifted seeds already-emitted output, never a collision, else a Check-lifted batch deadlocks its re-offer; and its DELIVERY rule keeps seeds off the code branch, which the existing code-lane MERGE-SAFETY gate already refuses. Section 9's ownership law puts each hook with its owner: the Check step and the lift are the stage layer's, admission is the merge queue's, the lane commit and the authoring-commit signal are the intake's, so all three modules are fenced. Section 13 requires the same authoring-commit event every path journals, so the age term is not silently dead for seeded stems.

## Scope in
A new module `squatch/seeds.py` owning the batch: `SEED_LIFT_SIGNAL` = `seed_lift`; `authored_seeds(worktree, stem, git) -> tuple[Seed, ...]` -- every `tickets/<x>/ticket.md` with `x != stem` that the worktree FILESYSTEM holds but the worktree's HEAD does not (untracked or modified, read through `Git.status`), each `Seed(stem, text, blob sha)`; `validate_batch(seeds, *, repo, plan, config, events, seeder) -> list[Finding]` (code `requisition_review`, every finding with a paved road): the count exceeds `config.seeding.max_seeds_per_admission` (road: split the batch, the plan's `-continue` shape); a seed without `source: seed` and `state: confirmed`; a seed that fails `lint_ticket` with `resolve_stem` over the on-disk stems plus the batch; a dependency cycle over the plane plus the batch (`cycle_through`); a seed whose stem already exists on main's tickets dir UNLESS a prior `seed_lift` signal of this seeder names it (the RE-RUN exemption -- foreign stems stay protected). `squatch/stages.py`: `_check` gains the seed step before the gates run: `authored_seeds` non-empty makes the run a seeding run, `validate_batch` findings join the invoice as `requisition_review` entries, and `RequisitionGate` (constructed over a resolver yielding every seed as a target, reviewed at the SEED'S authored tier) joins the gate tuple so each seed is reviewed with ONE render against its own text and Context closure -- `Context` paths resolved in the worktree, never a union over the batch; every gate result lands in `checks.json` per seed path. On a passing invoice the SEED LIFT runs as ONE effect keyed `lift/<stem>/<run_seq>/seeds`: each seed's text is written to the canonical `tickets/<x>/ticket.md` through the filesystem seam and committed by `Intake.commit(x, source="seed", state="confirmed")` -- the one lane, which lints again, pathspec-commits `squatch(<x>): ticket`, and journals the `ticket_intake` signal (the age term) -- then one `signal` with body `kind: seed_lift`, `seeder`, `run_seq`, and `seeds` (a map of stem to lifted blob sha) journals the batch; a non-seeding run journals nothing new and makes no review call. `squatch/merge.py`: MERGE-SAFETY gains `SeedSafety` (code `requisition_review`) beside `CodeLane`: for the run's `seed_lift` signal (none: pass), every named seed's canonical `tickets/<x>/ticket.md` blob sha on main equals the lifted sha AND the run's committed `tickets/<stem>/checks.json` carries a passing `requisition_review` entry for that seed path, else `fail` with the road `re-run the stem: a lifted seed has no recorded approval for the bytes on main`; the existing code-lane refusal of a branch carrying `tickets/**` commits is unchanged. `squatch/drain.py` is fenced per the ownership law as the scheduler whose after-every-merge re-scan makes the lifted seeds eligible; it changes only if the re-scan cannot see a lifted seed in the same invocation. `squatch/runner.py` is fenced as the terminal-write owner; it changes only if the seed step's outcome cannot ride the existing `Delivery`. Tests for every rule above; read `squatch/requisition.py` and `tests/test_requisition.py` in the worktree (they land with the `depends`), and read `squatch/gates.py`, `squatch/git.py`, `squatch/config.py`, `squatch/journal.py`, `squatch/artifacts.py`, and `tests/test_drain.py` there too (kept out of `Context` so the base Implement render clears the section 8 bound with headroom).

## Scope out
No Author-path change (the previous seed). No exit-read machinery, no phase report, no journal window materialization (the exit ticket's own concerns). No seeding of any ticket here: this seed builds the path; the first seeding run is `phase2-exit`. No drain intake review, no draft gate for seeds, no supervised-merge hold (Phase 6). No rename of a lifted seed, no overwrite of a foreign existing stem, no `tickets/**` code-lane exception. No new frontmatter field, config key beyond reading the shipped `seeding.max_seeds_per_admission`, cap, or journal event type beyond the `seed_lift` signal kind.

## Scope fence
- squatch/seeds.py
- squatch/stages.py
- squatch/merge.py
- squatch/tickets.py
- squatch/drain.py
- squatch/runner.py
- tests/test_seeds.py
- tests/test_stages.py
- tests/test_merge.py
- tests/test_terminal.py

## Acceptance criteria
- In `tests/test_seeds.py`, `authored_seeds` over a worktree holding two untracked seed files and the stem's own `run.md` returns exactly the two seeds with their blob shas, and returns nothing for a worktree with no foreign `ticket.md`.
- In `tests/test_seeds.py`, `validate_batch` reports a batch of four under the shipped cap of 3 with the split road, a seed lacking `source: seed`, a seed whose `Depends on` names a stem outside the plane and the batch, a batch cycle, and a seed whose stem already exists on main; the same existing stem passes when a prior `seed_lift` signal of this seeder names it.
- In `tests/test_terminal.py`, a seeding run under a `FakeLLM` scripted `implemented` then `approve` per seed then a review `approve` journals, in order: two `requisition_review` gate entries in `checks.json` (one per seed path), the `lift/<stem>/<run_seq>/seeds` effect intent and completion, one `ticket_intake` signal per seed with `source: seed` and `state: confirmed`, one `seed_lift` signal naming both seeds and their shas, then the review call; both `tickets/<seed>/ticket.md` files are committed on main byte-identical to the worktree copies.
- In `tests/test_terminal.py`, a seeding run whose second seed is scripted `snag` ends `gate_failed` with the snag finding naming that seed's path, no seed committed on main, and no `seed_lift` signal; a batch of four seeds ends `gate_failed` on the cap finding with no review call made.
- In `tests/test_terminal.py`, a re-offer of a seeding stem whose prior run already lifted its seeds lifts the same stems again without a collision finding, and a run of an ordinary ticket journals no `seed_lift` signal and no effect whose key starts with `llm/requisition_review/`.
- In `tests/test_merge.py`, an admission of a seeding branch whose lifted seed was edited on main after the lift is blocked with a `requisition_review` finding carrying the re-run road, and one whose seeds match their lifted shas and carry passing entries is admitted; an admission with no `seed_lift` signal runs no seed check.
- In `tests/test_seeds.py`, a drain over a plane holding one seeding ticket runs it, then dispatches a lifted seed that depends on the seeding stem in the SAME invocation after the seeding stem merges, and reports quiescence with both merged.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeds.py -q
uv run pytest tests/test_stages.py tests/test_merge.py tests/test_terminal.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the seed step cannot sit in `Stages._check` before the gate run without a second lift path or a second ticket-plane writer, if `Intake.commit` as landed cannot commit a `source: seed` stem from the canonical checkout while the worktree holds the run, if the MERGE-SAFETY tier in `squatch/merge.py` cannot host a second fast gate beside `CodeLane`, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
