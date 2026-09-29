---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- bug-gate-grammar
- report-inbox-triage

## Context
- tests/test_seeded_phase6_02.py

## Plan contract
- section 20

## Goal
Author the fourth fixed Phase 6 admission and preserve the terminal suffix.

## Why
The row-3 bug and intake boundaries must merge before escape attribution can be admitted.

## Scope in
Author confirmed source-seed `escape-column` and `phase6-continue-05`, plus new `tests/test_seeded_phase6_04.py`. Every payload and continuation cites section 20 alone and starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high. Render every authored seed at max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; never render section 19. The sole Context is merged `tests/test_seeded_phase6_02.py`; do not embed new or sibling-new paths.

Carry this exact shrinking suffix:
```yaml
- [escape-column, phase6-continue-05]
- [supervised-merge-hold, phase6-continue-06]
- [go-grade-machinery, go-grade-run, phase6-continue-07]
- [exit-receipt-machinery, phase6-continue-08]
- [phase6-exit]
```

`escape-column` depends on both `bug-gate-grammar` and `report-inbox-triage` and owns/fences `squatch/scorecard.py`, `squatch/git.py`, `squatch/retro.py`, `squatch/__main__.py`, `tests/test_scorecard.py`, `tests/test_git.py`, `tests/test_retro.py`, and `tests/test_cli.py`. Its attribution source is the already-custodied `Message.evidence.app_commit` of each resolved `bug_report`: the value is either one full 40-lowercase-hex commit or a closed `BASE..HEAD` pair of full hashes. The Git read operation accepts only commits reachable from current `HEAD`, walks a range on the ancestry path in first-parent order, and returns only commits carrying exactly one valid `squatch-ticket` and `squatch-reviewed-sha` trailer pair; malformed, missing-trailer, non-ancestor, reversed, empty, or foreign history yields no attribution. The effectful `status` and Retro callers read resolved Box reports and Git, then pass immutable `(report signature, merged ticket)` attribution observations into `RetroWindow`; `project_scorecard` remains pure. A report/ticket/surface increments escapes once only when that attributed merged ticket's completed Check invoice contains a pass for the surface; duplicates, failed/bypassed checks, unattributed reports, and surfaces absent from the attributed merge do not increment it. `squatch/git.py`, `squatch/retro.py`, `squatch/__main__.py`, `tests/test_git.py`, `tests/test_retro.py`, and `tests/test_cli.py` are measured on demand; scorecard and its focused test are Context.

`escape-column` partition: Embedded Context: `squatch/scorecard.py`, `tests/test_scorecard.py`; measured on-demand: `squatch/git.py`, `squatch/retro.py`, `squatch/__main__.py`, `tests/test_git.py`, `tests/test_retro.py`, `tests/test_cli.py`.

`supervised-merge-hold` is KNOWN-DEEP high/high, depends on `escape-column`, and owns/fences `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`, and new `tests/test_supervised_merge_hold.py`. It implements durable HELD admission after merge safety and integration checks but before main mutation, excludes held stems while preserving worktrees, releases through identity-bound `confirm` without a cap-rearming keep signal, rebase/regates against moved main, reconstructs holds on restart, and never holds the bootstrap self-build.

`supervised-merge-hold` partition: Embedded Context: none; measured on-demand: `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`.

`go-grade-machinery` depends on both `supervised-merge-hold` and `fixture-host-scaffold` and owns/fences `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`, and new `tests/test_go_grade.py`. It extends the committed harness to at least 50 planted defects under fixed USD 5.00 cap, runs harness-local Author prompt, records tickets and dependency graph in one closed report, adds operator-only `--record-go`, and never uses production `specs/author.md`.

`go-grade-machinery` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`; measured on-demand: none.

`go-grade-run` depends on `go-grade-machinery`, changes no code, and owns/fences only `tickets/go-grade-run/review-baseline-report.json`. It executes the merged harness once through the run lane; its committed report embeds mechanically recorded GO-or-NO-GO verdict signal identity, only the operator may turn an earned result into GO, and NO-GO is valid.

`go-grade-run` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`; measured on-demand: none.

`exit-receipt-machinery` depends on `go-grade-run` and owns/fences `squatch/artifacts.py`, new `eval/host_loop.py`, new `tests/test_host_loop.py`, and `tests/test_gates.py`. It registers closed writers for `host-loop-report.json` and `exit-receipt.json`; its harness launches supervised `serve` against `hosts/fixture/`, drives machine-actor confirms through the control inbox, records per-member `(member, driven scenario, observable, producing run)` evidence for at least three machine-ticket merges, report-to-regression bug loop, and escape attribution, and never produces terminal artifacts during its build.

`exit-receipt-machinery` partition: Embedded Context: `squatch/artifacts.py`, `tests/test_gates.py`; measured on-demand: `hosts/fixture/`.

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on every Phase 6 payload, and is last row's sole KNOWN-HARD high/high seed. It authors no successor and owns/fences only `tickets/phase6-exit/host-loop-report.json`, `tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`. It reads GO-grade verdict, accepts GO or NO-GO, proves three members, writes receipt digest, makes no engine-code edit; live-host K>=10 and real-host bug-loop evidence are forbidden exit inputs.

`phase6-exit` partition: Embedded Context: none; measured on-demand: none.

`phase6-continue-05` depends on `escape-column`. Owns `tickets`, `tests/test_seeded_phase6_05.py`; Context: `tests/test_seeded_phase6_03.py`.

`phase6-continue-06` depends on `supervised-merge-hold`. Owns `tickets`, `tests/test_seeded_phase6_06.py`; Context: `tests/test_seeded_phase6_04.py`.

`phase6-continue-07` depends on `go-grade-machinery`, `go-grade-run`. Owns `tickets`, `tests/test_seeded_phase6_07.py`; Context: `tests/test_seeded_phase6_05.py`.

`phase6-continue-08` depends on `exit-receipt-machinery`. Owns `tickets`, `tests/test_seeded_phase6_08.py`; Context: `tests/test_seeded_phase6_06.py`.

The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail.

## Scope out
Do not implement a payload, use sibling-new Context, render section 19, or add successors.

## Scope fence
- tickets
- tests/test_seeded_phase6_04.py

## Acceptance criteria
- `tests/test_seeded_phase6_04.py` pins the escape row, remaining contracts, and terminal custody.
- `tests/test_seeded_phase6_04.py` proves section-20-only max-effort renders and the terminal row.

## Verification
```
uv run pytest tests/test_seeded_phase6_04.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, overflow, or successor.

## Time budget
- expected: 75m
- stuck: 150m
