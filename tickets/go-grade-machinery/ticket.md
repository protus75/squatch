---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- supervised-merge-hold
- fixture-host-scaffold

## Context

## Plan contract
- section 20

## Goal
Build the bounded GO-grade harness and registered baseline report.

## Why
A committed, identity-bound baseline must precede terminal host-loop evidence.

## Scope in
Extend the committed harness to at least 50 planted defects under a fixed USD 5.00 cap.
The harness-local Author prompt is inline in `eval/harness.py`; defects are
planted at runtime, so no `eval/fixtures/` or prompt file is added. It runs the
harness-local Author prompt and never uses production `specs/author.md` as its
Author prompt (reading its version for baseline identity remains required).
Record authored tickets and their dependency graph for operator judgment.

Register closed `review-baseline-report.json` fields for planted-defect count,
spend, authored tickets, dependency graph, and verdict-signal identity in
`squatch/artifacts.py`; register its validator in `squatch/stages.py`'s
`KNOWN_ARTIFACTS` so ordinary lift validates and counts it through
`completed_output_lift`. Supply the canonical report producer/writer for the
separate `go-grade-run` ordinary run lane; build tests use injected seams,
never produce that run's terminal report during this build.

The operator-only `--record-go` appends the `review_baseline` signal read by
unchanged `resolve_baseline`. Ordinary harness runs still append the NO-GO
review_baseline signal and run_seq keying is unchanged; `--record-go` only
appends a GO body for an earned result after operator judgment, never rewrites
prior signals. No non-operator path can write verdict GO. The recorded signal
identity equals the report's verdict-signal identity. Record nonempty exercised
tiers, exactly {review, author} routing identity, and spec_major matching the
current specs so the unchanged reader can bind the GO body.
Preserve `test_run_scores_every_fixture_and_journals_the_no_go_signal` and
`test_rerun_after_a_recorded_verdict_takes_a_fresh_sequence_and_calls_again`.

Embedded Context: none. Measured on-demand worktree reads:
`eval/harness.py`, `squatch/artifacts.py`, `squatch/stages.py`,
`tests/test_eval_harness.py`, `tests/test_stages.py`. Read these before editing;
their combined size exceeds render headroom. New `tests/test_go_grade.py` is
not Context. Read `squatch/baseline.py` only to observe its unchanged public reader.

## Scope out
Do not modify the baseline reader, production Author prompt, or fixture files; do not execute the real run or record production GO during construction.

## Scope fence
- eval/harness.py
- squatch/artifacts.py
- squatch/stages.py
- tests/test_eval_harness.py
- tests/test_stages.py
- tests/test_go_grade.py

## Acceptance criteria
- `tests/test_go_grade.py` proves runtime planting of at least 50 defects, the fixed USD 5.00 cap including Author spend, local Author execution, and recorded tickets/dependency graph.
- `tests/test_go_grade.py` and `tests/test_stages.py` prove closed report validation, unknown-field refusal, and ordinary-lane lift/counting.
- `tests/test_go_grade.py` alone proves an operator `--record-go` body resolves to GO/binds=true through unchanged `resolve_baseline`, with nonempty tiers, exactly {review, author} identity, and matching spec_major. It also proves no non-operator path writes GO and recorded signal identity equals report verdict-signal identity.
- `tests/test_eval_harness.py` preserves ordinary NO-GO and run_seq rerun behavior; no real report is produced by this build.

## Verification
```
uv run pytest tests/test_go_grade.py tests/test_eval_harness.py tests/test_stages.py -q
uv run pytest tests/test_baseline.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, unregistered or fabricated evidence, overflow, or successors.

## Time budget
- expected: 75m
- stuck: 150m
