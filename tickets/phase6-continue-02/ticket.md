---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- core-drift-activation
- migrate-config

## Context
- tests/test_seeded_phase6_core.py

## Plan contract
- section 20

## Goal
Author the second fixed Phase 6 feature row and preserve the finite suffix.

## Why
Both first-row boundaries must merge before the host documentation and fixture
can be admitted with their correct existing-path partition.

## Scope in
Author confirmed source-seed medium/medium `host-contract-doc`, `fixture-host-scaffold`, and `phase6-continue-03`, plus new `tests/test_seeded_phase6_02.py`. It authors row 2. Every payload and continuation cites section 20 alone and starts medium/medium unless marked KNOWN-DEEP or KNOWN-HARD high/high. Render every authored seed at max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; never render section 19.

The sole Context is merged `tests/test_seeded_phase6_core.py`: `tests/test_seeded_phase6_01.py` was sibling-new when this continuation was authored. Do not embed new or sibling-new paths.

Every numbered continuation owns only `tickets` plus its matching new `tests/test_seeded_phase6_<nn>.py`, embeds the immediately preceding merged Phase 6 seeded test as its sole Context, depends on every payload in its row, pins the exact edges and contracts plus max-effort headroom, and carries the shrinking suffix. Merged means already on main at authoring time. The sibling-new seeded test created alongside that continuation is excluded because new and sibling-new paths are never Context. `phase6-continue-03` passes this same rule forward for every later numbered continuation.

Carry this exact shrinking suffix:
```yaml
- [host-contract-doc, fixture-host-scaffold, phase6-continue-03]
- [bug-gate-grammar, report-inbox-triage, phase6-continue-04]
- [escape-column, phase6-continue-05]
- [supervised-merge-hold, phase6-continue-06]
- [go-grade-machinery, go-grade-run, phase6-continue-07]
- [exit-receipt-machinery, phase6-continue-08]
- [phase6-exit]
```

`host-contract-doc` depends on `migrate-config` and owns/fences new `docs/host-contract.md` and new `tests/test_host_contract.py`. It commits the section 15 host schema's copyable commented `review`/`merge` example, seam inventory, report-inbox contract, managed-file ownership rule, migration/cutover steps, and explicitly excludes foreign process-state adoption. It has no production-code write and no Context.

`host-contract-doc` partition: Embedded Context: none; measured on-demand: none.

`fixture-host-scaffold` depends on both `host-contract-doc` and `core-drift-activation` and owns/fences new `hosts/fixture/` plus new `tests/test_fixture_host.py`. The fixture contains a host-root config profile, miniature deterministic app, replay-runner command, closed scenario list, bounded version-1 report fixtures, one merge-base regression defect, one machine-introduced escape scenario, and a scripted agent-CLI provider row serving Author/Implement/Review at zero model spend. It changes no engine module and has no embedded Context: sibling-new `docs/host-contract.md` is excluded at authoring and becomes an ordinary worktree read after its required `host-contract-doc` dependency merges.

`fixture-host-scaffold` partition: Embedded Context: none; measured on-demand: none.

`bug-gate-grammar` depends on `fixture-host-scaffold` and owns/fences `squatch/tickets.py`, `squatch/gates.py`, `squatch/stages.py`, `tests/test_tickets.py`, `tests/test_gates.py`, and new `tests/test_bug_gate.py`. It adds `kind: bug`, mandatory `## Regression`, and the branch-head-pass/merge-base-with-`carries`-overlay- fail hard gate; a missing test at base is never accepted as defect evidence. Existing `squatch/tickets.py`, `squatch/stages.py`, `tests/test_tickets.py`, and composition callers are measured on demand; the gate parser and focused `tests/test_gates.py` are Context.

`bug-gate-grammar` partition: Embedded Context: `squatch/gates.py`, `tests/test_gates.py`; measured on-demand: `squatch/tickets.py`, `squatch/stages.py`, `tests/test_tickets.py`.

`report-inbox-triage` depends on `bug-gate-grammar` and owns/fences new `squatch/inbox.py`, `squatch/box.py`, `squatch/triage.py`, `squatch/author.py`, `squatch/daemon.py`, `squatch/serve.py`, `tests/test_box.py`, `tests/test_triage.py`, `tests/test_author.py`, `tests/test_serve.py`, and new `tests/test_inbox.py`. It enforces the version-1 report schema, metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps, copies bounded evidence into durable Box custody before recording the message, wires the daemon and live serve consumers, and makes sequential triage author `kind: bug` tickets whose evidence and `## Regression` survive intake. Daemon/Author/Serve roots, `squatch/triage.py`, their large tests, and delimiter-carrying `tests/test_triage.py` are measured on-demand exceptions; the Box seam and focused `tests/test_box.py` are Context.

`report-inbox-triage` partition: Embedded Context: `squatch/box.py`, `tests/test_box.py`; measured on-demand: `squatch/triage.py`, `squatch/author.py`, `squatch/daemon.py`, `squatch/serve.py`, `tests/test_author.py`, `tests/test_triage.py`, `tests/test_serve.py`.

`escape-column` depends on both `bug-gate-grammar` and `report-inbox-triage` and owns/fences `squatch/scorecard.py`, `squatch/git.py`, `tests/test_scorecard.py`, and `tests/test_git.py`. It adds the squash-trailer read operation and deterministic bug-to-merged-ticket-or-bounded-range attribution, increments escapes only for surfaces that passed the attributed merges, and leaves unattributed or foreign history out. `squatch/git.py` and `tests/test_git.py` may be measured on demand; scorecard and its test are Context.

`escape-column` partition: Embedded Context: `squatch/scorecard.py`, `tests/test_scorecard.py`; measured on-demand: `squatch/git.py`, `tests/test_git.py`.

`supervised-merge-hold` is KNOWN-DEEP high/high, depends on `escape-column`, and owns/fences `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`, and new `tests/test_supervised_merge_hold.py`. It implements the durable HELD admission state after merge safety and integration checks but before main mutation, excludes held stems from dispatch while preserving their worktrees, releases through identity-bound `confirm` without a cap-rearming keep signal, rebase/regates against moved main, reconstructs holds on restart, and never holds the bootstrap self-build. Every existing production root and broad suite in this fence is a measured on-demand exception; the new focused test is not Context.

`supervised-merge-hold` partition: Embedded Context: none; measured on-demand: `squatch/merge.py`, `squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`, `tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`.

`go-grade-machinery` depends on both `supervised-merge-hold` and `fixture-host-scaffold` and owns/fences `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`, and new `tests/test_go_grade.py`. It extends the committed harness to at least 50 planted defects under the fixed USD 5.00 cap, runs the harness-local Author prompt, records the authored tickets and dependency graph in one closed report, and adds operator-only `--record-go`; production `specs/author.md` is never used. Existing harness/artifact modules and `tests/test_eval_harness.py` are Context.

`go-grade-machinery` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`, `tests/test_eval_harness.py`; measured on-demand: none.

`go-grade-run` depends on `go-grade-machinery`, changes no code, and owns/fences only `tickets/go-grade-run/review-baseline-report.json`. It executes the merged harness once through the run lane. The committed report embeds its mechanically recorded GO-or-NO-GO verdict signal identity; only the operator may turn an earned result into GO, so NO-GO is a valid self-build result. Its Context is `eval/harness.py` and `squatch/artifacts.py`.

`go-grade-run` partition: Embedded Context: `eval/harness.py`, `squatch/artifacts.py`; measured on-demand: none.

`exit-receipt-machinery` depends on `go-grade-run` and owns/fences `squatch/artifacts.py`, new `eval/host_loop.py`, new `tests/test_host_loop.py`, and `tests/test_gates.py`. It registers closed writers for `host-loop-report.json` and `exit-receipt.json`; the host-loop harness launches supervised `serve` as a subprocess against `hosts/fixture/`, drives machine-actor confirms through the control inbox, and records per-member `(member, driven scenario, observable, producing run)` evidence for at least three machine-ticket merges, the report-to-regression bug loop, and escape attribution. The machinery never produces terminal artifacts during its own build. Existing artifact code/tests `squatch/artifacts.py` and `tests/test_gates.py` are embedded Context; the directory `hosts/fixture/` is a named measured on-demand worktree read and is never an embedded Context entry.

`exit-receipt-machinery` partition: Embedded Context: `squatch/artifacts.py`, `tests/test_gates.py`; measured on-demand: `hosts/fixture/`.

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on every Phase 6 payload, and is the last row's sole KNOWN-HARD high/high seed. It authors no successor and owns/fences only `tickets/phase6-exit/host-loop-report.json`, `tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`. It runs the registered host-loop producer, reads the committed GO-grade report and its embedded verdict identity, accepts GO or NO-GO, proves the three closed host-loop members, writes the receipt digest, and performs no engine-code edit. Live-host K>=10 and real-host bug-loop evidence remain operator post-cutover acceptance and are forbidden as exit inputs. Every fenced path is terminal output or a new focused test, so it has no Context. It has no successor and no continuation tail is authored.

`phase6-exit` partition: Embedded Context: none; measured on-demand: none.

`phase6-continue-03` depends on `host-contract-doc`, `fixture-host-scaffold`. It owns only `tickets`, `tests/test_seeded_phase6_03.py` and has sole Context `tests/test_seeded_phase6_01.py`.

`phase6-continue-04` depends on `bug-gate-grammar`, `report-inbox-triage`. It owns only `tickets`, `tests/test_seeded_phase6_04.py` and has sole Context `tests/test_seeded_phase6_02.py`.

`phase6-continue-05` depends on `escape-column`. It owns only `tickets`, `tests/test_seeded_phase6_05.py` and has sole Context `tests/test_seeded_phase6_03.py`.

`phase6-continue-06` depends on `supervised-merge-hold`. It owns only `tickets`, `tests/test_seeded_phase6_06.py` and has sole Context `tests/test_seeded_phase6_04.py`.

`phase6-continue-07` depends on `go-grade-machinery`, `go-grade-run`. It owns only `tickets`, `tests/test_seeded_phase6_07.py` and has sole Context `tests/test_seeded_phase6_05.py`.

`phase6-continue-08` depends on `exit-receipt-machinery`. It owns only `tickets`, `tests/test_seeded_phase6_08.py` and has sole Context `tests/test_seeded_phase6_06.py`.

The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail.

## Scope out
Do not implement a payload, use sibling-new Context, cite or render section
19, alter the registry, or author a successor after `phase6-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase6_02.py

## Acceptance criteria
- `tests/test_seeded_phase6_02.py` pins row 2, all remaining direct edges, fences, partitions, behavior, tiers, and terminal custody.
- `tests/test_seeded_phase6_02.py` proves every emitted ticket uses section 20 alone and renders within max-effort headroom.
- `tests/test_seeded_phase6_02.py` proves the terminal row is `phase6-exit` alone with only its two receipts and focused proof and no successor.

## Verification
```
uv run pytest tests/test_seeded_phase6_02.py -q
uv run pytest -q
```

## Definition of rejected
Reject a changed row, edge, owner, partition, behavior contract, section
citation, render overflow, or terminal successor.

## Time budget
- expected: 75m
- stuck: 150m
