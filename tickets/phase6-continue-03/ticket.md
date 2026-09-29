---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- host-contract-doc
- fixture-host-scaffold

## Context
- tests/test_seeded_phase6_01.py

## Plan contract
- section 20

## Goal
Row 3

## Why
Plan repaired.

## Scope in
Author `bug-gate-grammar`, `report-inbox-triage`, and `phase6-continue-04`. Every payload and continuation cites section 20 alone and starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high. Render at max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; never render section 19.

Every numbered continuation owns only `tickets` plus its new `tests/test_seeded_phase6_<nn>.py`, embeds the immediately preceding merged Phase 6 seeded test as sole Context, depends on every row payload, and carries this suffix:
```yaml
- [bug-gate-grammar, report-inbox-triage, phase6-continue-04]
- [escape-column, phase6-continue-05]
- [supervised-merge-hold, phase6-continue-06]
- [go-grade-machinery, go-grade-run, phase6-continue-07]
- [exit-receipt-machinery, phase6-continue-08]
- [phase6-exit]
```

`bug-gate-grammar` depends on `fixture-host-scaffold` and owns/fences `squatch/tickets.py`, `squatch/gates.py`, `squatch/stages.py`, `tests/test_tickets.py`, `tests/test_gates.py`, and new `tests/test_bug_gate.py`. It adds `kind: bug`, mandatory `## Regression`, and the branch-head-pass/merge-base-with-`carries`-overlay-fail hard gate; a missing test at base is never accepted as defect evidence.

`bug-gate-grammar` partition: Embedded Context: `squatch/gates.py`, `tests/test_gates.py`; measured on-demand: `squatch/tickets.py`, `squatch/stages.py`, `tests/test_tickets.py`.

`report-inbox-triage` depends on `bug-gate-grammar` and owns/fences new `squatch/inbox.py`, `squatch/box.py`, `squatch/triage.py`, `squatch/author.py`, `squatch/daemon.py`, `tests/test_box.py`, `tests/test_triage.py`, `tests/test_author.py`, and new `tests/test_inbox.py`. It enforces the version-1 report schema, metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps, copies bounded evidence into durable Box custody before recording the message, wires the daemon consumer, and makes sequential triage author `kind: bug` tickets whose evidence and `## Regression` survive intake.

`report-inbox-triage` partition: Embedded Context: `squatch/box.py`, `squatch/triage.py`, `tests/test_box.py`; measured on-demand: `squatch/author.py`, `squatch/daemon.py`, `tests/test_author.py`, `tests/test_triage.py`.

`escape-column` depends on both `bug-gate-grammar` and `report-inbox-triage` and owns/fences `squatch/scorecard.py`, `squatch/git.py`, `tests/test_scorecard.py`, and `tests/test_git.py`. It adds the squash-trailer read operation and deterministic bug-to-merged-ticket-or-bounded-range attribution, increments escapes only for surfaces that passed attributed merges, and leaves unattributed or foreign history out.

`escape-column` partition: Embedded Context: `squatch/scorecard.py`, `tests/test_scorecard.py`; measured on-demand: `squatch/git.py`, `tests/test_git.py`.

`supervised-merge-hold` is KNOWN-DEEP high/high, depends on `escape-column`, and owns/fences `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`, and new `tests/test_supervised_merge_hold.py`. It implements durable HELD admission after merge safety and integration checks but before main mutation, excludes held stems while preserving worktrees, releases through identity-bound `confirm` without a cap-rearming keep signal, rebase/regates against moved main, reconstructs holds on restart, and never holds the bootstrap self-build.

`supervised-merge-hold` partition: Embedded Context: none; measured on-demand: `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`.

`go-grade-machinery` depends on both `supervised-merge-hold` and `fixture-host-scaffold` and owns/fences `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`, and new `tests/test_go_grade.py`. It extends the harness to at least 50 planted defects under fixed USD 5.00 cap, runs harness-local Author prompt, records tickets and dependency graph in one closed report, adds operator-only `--record-go`, and never uses production `specs/author.md`.

`go-grade-machinery` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`; measured on-demand: none.

`go-grade-run` depends on `go-grade-machinery`, changes no code, and owns/fences only `tickets/go-grade-run/review-baseline-report.json`. It executes the merged harness once through the run lane; its committed report embeds mechanically recorded GO-or-NO-GO verdict signal identity, only the operator may turn an earned result into GO, and NO-GO is valid. Its Context is `eval/harness.py` and `squatch/artifacts.py`.

`go-grade-run` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`; measured on-demand: none.

`exit-receipt-machinery` depends on `go-grade-run` and owns/fences `squatch/artifacts.py`, new `eval/host_loop.py`, new `tests/test_host_loop.py`, and `tests/test_gates.py`. It registers closed writers for `host-loop-report.json` and `exit-receipt.json`; its harness launches supervised `serve` against `hosts/fixture/`, drives machine-actor confirms through the control inbox, records per-member `(member, driven scenario, observable, producing run)` evidence for at least three machine-ticket merges, report-to-regression bug loop, and escape attribution, and never produces terminal artifacts during its build.

`exit-receipt-machinery` partition: Embedded Context: `squatch/artifacts.py`, `tests/test_gates.py`; measured on-demand: `hosts/fixture/`.

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on every Phase 6 payload, and is last row's sole KNOWN-HARD high/high seed. It authors no successor and owns/fences only `tickets/phase6-exit/host-loop-report.json`, `tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`. It reads GO-grade verdict, accepts GO or NO-GO, proves three members, writes receipt digest, makes no engine-code edit; live-host K>=10 and real-host bug-loop evidence are forbidden exit inputs.

`phase6-exit` partition: Embedded Context: none; measured on-demand: none.

`phase6-continue-04` depends on `bug-gate-grammar`, `report-inbox-triage`. Owns `tickets`, `tests/test_seeded_phase6_04.py`; Context: `tests/test_seeded_phase6_02.py`.

`phase6-continue-05` depends on `escape-column`. Owns `tickets`, `tests/test_seeded_phase6_05.py`; Context: `tests/test_seeded_phase6_03.py`.

`phase6-continue-06` depends on `supervised-merge-hold`. Owns `tickets`, `tests/test_seeded_phase6_06.py`; Context: `tests/test_seeded_phase6_04.py`.

`phase6-continue-07` depends on `go-grade-machinery`, `go-grade-run`. Owns `tickets`, `tests/test_seeded_phase6_07.py`; Context: `tests/test_seeded_phase6_05.py`.

`phase6-continue-08` depends on `exit-receipt-machinery`. Owns `tickets`, `tests/test_seeded_phase6_08.py`; Context: `tests/test_seeded_phase6_06.py`.

The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail.

## Scope out
Do not implement payloads, use sibling-new Context, render section 19, or add successors.

## Scope fence
- tickets
- tests/test_seeded_phase6_03.py

## Acceptance criteria
- `tests/test_seeded_phase6_03.py` pins row 3, contracts, and terminal custody.
- `tests/test_seeded_phase6_03.py` proves section-20-only max-effort renders and the terminal row.

## Verification
```
uv run pytest tests/test_seeded_phase6_03.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, overflow, or successor.

## Time budget
- expected: 75m
- stuck: 150m
