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
on `fixture-host-scaffold`, fences ticket/gate parser paths plus new
`tests/test_bug_gate.py`, adds `kind: bug`, mandatory `## Regression`, and the
branch-head-pass/merge-base-with-`carries`-overlay-fail hard gate; missing base
tests are never defect evidence. `report-inbox-triage` depends on it, fences
new `squatch/inbox.py`, Box/Triage/Author/Daemon seams and focused tests, caps
metadata-first replay files at 1 MiB and log excerpts at 64 KiB, copies bounded
evidence into durable Box custody before recording, and preserves `kind: bug` evidence and
`## Regression` through sequential triage.

`escape-column` depends on both row-3 features, fences scorecard/Git and their
tests, and adds squash-trailer reading with deterministic bug attribution;
only surfaces passing attributed merges gain escapes, foreign or unattributed
history is excluded. `supervised-merge-hold` is KNOWN-DEEP high/high, depends
on `escape-column`, fences merge/baseline/control/CLI/stages/drain/runner and
their listed tests plus new `tests/test_supervised_merge_hold.py`, and provides
durable HELD admission, identity-bound `confirm`, restart reconstruction,
rebase/regate, and no bootstrap self-build hold. Existing roots and broad
suites are measured on-demand; the new focused test is not Context.

`go-grade-machinery` depends on `supervised-merge-hold` and
`fixture-host-scaffold`, fences `eval/harness.py`, `squatch/artifacts.py`,
`tests/test_harness.py`, and new `tests/test_go_grade.py`; its existing paths
are Context. It has at least 50 planted defects, fixed USD 5.00 cap,
harness-local Author prompt, closed report, and operator-only `--record-go`;
production `specs/author.md` is never used. `go-grade-run` depends on it,
changes no code, fences only
`tickets/go-grade-run/review-baseline-report.json`, has Context
`eval/harness.py` and `squatch/artifacts.py`, and records GO-or-NO-GO signal
identity, with NO-GO valid.

`exit-receipt-machinery` depends on `go-grade-run`, fences
`squatch/artifacts.py`, new `eval/host_loop.py`, new `tests/test_host_loop.py`,
and `tests/test_artifacts.py`; artifact code/tests are Context and
`hosts/fixture/` is a measured on-demand worktree read, never embedded. It
registers closed receipt writers and runs supervised `serve` with control-inbox
machine confirms, recording per-member evidence for three machine merges, the
report-to-regression bug loop, and escape attribution; it never produces
terminal artifacts during its build. `phase6-continue-08` depends on it.

The terminal row contains `phase6-exit` alone. It is KNOWN-HARD high/high,
depends on `exit-receipt-machinery`, owns/fences only
`tickets/phase6-exit/host-loop-report.json`,
`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`,
has no Context, reads the committed GO-grade verdict identity, accepts GO or
NO-GO, proves the three closed members, writes the receipt digest, makes no
engine-code edit, and has no successor.

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
