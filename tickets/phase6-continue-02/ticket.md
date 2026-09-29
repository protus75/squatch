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
Author confirmed `host-contract-doc`, `fixture-host-scaffold`, and
`phase6-continue-03`, plus `tests/test_seeded_phase6_02.py`. Cite section 20
alone, start medium/medium, and render every authored seed at max effort within
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. The sole Context is the
merged `tests/test_seeded_phase6_core.py`; never embed this admission's new
`tests/test_seeded_phase6_02.py` or sibling-new paths.

`host-contract-doc` depends on `migrate-config`, owns/fences new
`docs/host-contract.md` and new `tests/test_host_contract.py`, has no
production-code write and no Context. It commits the section 15 host schema's
copyable commented `review`/`merge` example, seam inventory, report-inbox
contract, managed-file ownership rule, migration/cutover steps, and explicitly
excludes foreign process-state adoption.

`fixture-host-scaffold` depends on both `host-contract-doc` and
`core-drift-activation`, owns/fences new `hosts/fixture/` and new
`tests/test_fixture_host.py`, changes no engine module, and has no embedded
Context. It supplies a host-root config profile, miniature deterministic app,
replay-runner command, closed scenario list, bounded version-1 report fixtures,
one merge-base regression defect, one machine-introduced escape scenario, and a
scripted agent-CLI provider row serving Author/Implement/Review at zero model
spend. Sibling-new `docs/host-contract.md` is excluded at authoring and becomes
an ordinary worktree read after its required dependency merges.

`phase6-continue-03` depends on both `host-contract-doc` and
`fixture-host-scaffold`, owns only `tickets` plus new
`tests/test_seeded_phase6_03.py`, and embeds the immediately preceding merged
Phase 6 seeded test as its sole Context. It authors row 3.

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

Pin every following row's exact direct edges, owner/fence, Context/on-demand
partition, and behavior contract from section 20. `bug-gate-grammar` depends
on `fixture-host-scaffold`, owns/fences `squatch/tickets.py`,
`squatch/gates.py`, `squatch/stages.py`, `tests/test_tickets.py`,
`tests/test_gates.py`, and new `tests/test_bug_gate.py`. `squatch/stages.py`
and its composition callers are measured on-demand exceptions; the ticket/gate
parsers `squatch/tickets.py` and `squatch/gates.py` plus focused
`tests/test_tickets.py` and `tests/test_gates.py` are Context. It adds `kind: bug`, mandatory
`## Regression`, and the branch-head-pass/merge-base-with-`carries`-overlay-
fail hard gate; a missing test at base is never accepted as defect evidence.
`report-inbox-triage` depends on `bug-gate-grammar`, owns/fences new
`squatch/inbox.py`, `squatch/box.py`, `squatch/triage.py`,
`squatch/author.py`, `squatch/daemon.py`, `tests/test_box.py`,
`tests/test_triage.py`, `tests/test_author.py`, and new
`tests/test_inbox.py`. Daemon/Author roots and their large tests are measured
on-demand exceptions; existing Box/Triage seams `squatch/box.py` and
`squatch/triage.py` plus focused `tests/test_box.py` and
`tests/test_triage.py` are Context.
It enforces the version-1 report schema, metadata-first 1 MiB replay-file and
64 KiB log-excerpt caps, copies bounded evidence into durable Box custody
before recording the message, wires the daemon consumer, and makes sequential
triage author `kind: bug` tickets whose evidence and `## Regression` survive
intake. `phase6-continue-04` depends on both `bug-gate-grammar` and
`report-inbox-triage`.

Every numbered continuation passes this same custody rule forward: it owns
only `tickets` plus its matching new `tests/test_seeded_phase6_<nn>.py`,
embeds the immediately preceding merged Phase 6 seeded test as its sole
Context, depends on every payload in its row, and carries the shrinking
suffix. The exact remaining continuation partitions are:
`phase6-continue-03` owns only `tickets` plus new
`tests/test_seeded_phase6_03.py` and has sole Context
`tests/test_seeded_phase6_02.py`; `phase6-continue-04` owns only `tickets`
plus new `tests/test_seeded_phase6_04.py` and has sole Context
`tests/test_seeded_phase6_03.py`; `phase6-continue-05` owns only `tickets`
plus new `tests/test_seeded_phase6_05.py` and has sole Context
`tests/test_seeded_phase6_04.py`; `phase6-continue-06` owns only `tickets`
plus new `tests/test_seeded_phase6_06.py` and has sole Context
`tests/test_seeded_phase6_05.py`; `phase6-continue-07` owns only `tickets`
plus new `tests/test_seeded_phase6_07.py` and has sole Context
`tests/test_seeded_phase6_06.py`; and `phase6-continue-08` owns only `tickets`
plus new `tests/test_seeded_phase6_08.py` and has sole Context
`tests/test_seeded_phase6_07.py`. `phase6-continue-03` passes this same rule
forward for every later numbered continuation.

`escape-column` depends on both `bug-gate-grammar` and
`report-inbox-triage`, owns/fences `squatch/scorecard.py`, `squatch/git.py`,
`tests/test_scorecard.py`, and `tests/test_git.py`. `squatch/git.py` and
`tests/test_git.py` may be measured on-demand exceptions; `squatch/scorecard.py`
and `tests/test_scorecard.py` are Context. It adds the squash-trailer read operation and deterministic
bug-to-merged-ticket-or-bounded-range attribution, increments escapes only for
surfaces that passed the attributed merges, and leaves unattributed or foreign
history out. `phase6-continue-05` depends on `escape-column`.

`supervised-merge-hold` is KNOWN-DEEP high/high, depends on `escape-column`,
and owns/fences `squatch/merge.py`, `squatch/baseline.py`,
`squatch/control.py`, `squatch/__main__.py`, `squatch/stages.py`,
`squatch/drain.py`, `squatch/runner.py`, `tests/test_merge.py`,
`tests/test_baseline.py`, `tests/test_control_cli.py`, `tests/test_cli.py`,
`tests/test_drain.py`, and new `tests/test_supervised_merge_hold.py`. Every
existing production root and broad suite in this fence is a measured on-demand
exception; the new focused test is not Context. It implements durable HELD
admission after merge safety and integration checks but before main mutation,
excludes held stems from dispatch while preserving their worktrees, releases
through identity-bound `confirm` without a cap-rearming keep signal,
rebase/regates against moved main, reconstructs holds on restart, and never
holds the bootstrap self-build. `phase6-continue-06` depends on
`supervised-merge-hold`.

`go-grade-machinery` depends on both `supervised-merge-hold` and
`fixture-host-scaffold`, owns/fences `eval/harness.py`,
`squatch/artifacts.py`, `tests/test_eval_harness.py`, and new
`tests/test_go_grade.py`; existing harness/artifact modules and
`tests/test_eval_harness.py` are Context: exactly `eval/harness.py`,
`squatch/artifacts.py`, and `tests/test_eval_harness.py`. It extends the committed harness to at
least 50 planted defects under the fixed USD 5.00 cap, runs the harness-local
Author prompt, records the authored tickets and dependency graph in one closed
report, and adds operator-only `--record-go`; production `specs/author.md` is
never used. `go-grade-run` depends on `go-grade-machinery`, changes no code,
owns/fences only `tickets/go-grade-run/review-baseline-report.json`, and has
Context exactly `eval/harness.py` and `squatch/artifacts.py`. Its committed report
embeds its mechanically recorded GO-or-NO-GO verdict signal identity; only the
operator may turn an earned result into GO, so NO-GO is valid.
`phase6-continue-07` depends on both `go-grade-machinery` and `go-grade-run`.

`exit-receipt-machinery` depends on `go-grade-run`, owns/fences
`squatch/artifacts.py`, new `eval/host_loop.py`, new
`tests/test_host_loop.py`, and `tests/test_gates.py`. Existing artifact
code/tests `squatch/artifacts.py` and `tests/test_gates.py` are embedded Context;
`hosts/fixture/` is a named measured on-demand
worktree read and is never an embedded Context entry. It registers closed
writers for `host-loop-report.json` and `exit-receipt.json`; the host-loop
harness launches supervised `serve` as a subprocess against `hosts/fixture/`,
drives machine-actor confirms through the control inbox, and records per-member
`(member, driven scenario, observable, producing run)` evidence for at least
three machine-ticket merges, the report-to-regression bug loop, and escape
attribution. It never produces terminal artifacts during its own build.
`phase6-continue-08` depends on `exit-receipt-machinery`.

The terminal row contains `phase6-exit` alone. It is KNOWN-HARD high/high,
depends on `exit-receipt-machinery`, owns/fences only
`tickets/phase6-exit/host-loop-report.json`,
`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`.
Every fenced path is terminal output or a new focused test, so it has no
Context. It runs the registered host-loop producer, reads the committed
GO-grade report and its embedded verdict identity, accepts GO or NO-GO, proves
the three closed host-loop members, writes the receipt digest, makes no
engine-code edit, and has no successor. Live-host K>=10 and real-host bug-loop
evidence remain operator post-cutover acceptance and are forbidden as exit
inputs.

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
