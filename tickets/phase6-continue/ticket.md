---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- core-renderer
- core-drift-classifier

## Context
- tests/test_seeded_phase5_04.py

## Plan contract
- section 20

## Goal
Author the first fixed Phase 6 feature row and preserve the complete finite
Phase 6 suffix.

## Why
Phase 6 must advance from the admitted core without inventing an owner,
dependency, Context partition, behavior boundary, or terminal successor.

## Scope in
Use merged `tests/test_seeded_phase5_04.py` as the sole continuation Context.
Never embed same-admission `tests/test_seeded_phase6_core.py`, new
`tests/test_seeded_phase6_01.py`, or sibling-new `squatch/hostfiles.py` and
`tests/test_hostfiles.py`. Cite section 20 alone; no historical or live
section 19 render is accepted. Render every authored seed at max effort within
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

Carry this exact shrinking suffix:
```yaml
- [core-drift-activation, migrate-config, phase6-continue-02]
- [host-contract-doc, fixture-host-scaffold, phase6-continue-03]
- [bug-gate-grammar, report-inbox-triage, phase6-continue-04]
- [escape-column, phase6-continue-05]
- [supervised-merge-hold, phase6-continue-06]
- [go-grade-machinery, go-grade-run, phase6-continue-07]
- [exit-receipt-machinery, phase6-continue-08]
- [phase6-exit]
```
Author the first row now. Every payload is confirmed, source seed, cites
section 20 alone, and starts medium/medium unless marked KNOWN-DEEP. Each
numbered continuation owns only `tickets` plus its matching new
`tests/test_seeded_phase6_<nn>.py`, embeds the immediately preceding merged
Phase 6 seeded test as its sole Context, depends on every payload in its row,
pins the exact edges and contracts plus max-effort headroom, and carries the
shrinking suffix. Existing paths in a payload fence are Context unless
explicitly named below as measured on-demand exceptions; new and sibling-new
paths are never Context.

`core-drift-activation` depends on `core-drift-classifier` and owns/fences
`squatch/hostfiles.py`, `squatch/gates.py`, `squatch/config.py`,
`squatch/merge.py`, `squatch/providers.py`, `squatch/__main__.py`,
`tests/test_hostfiles.py`, `tests/test_gates.py`, `tests/test_merge.py`,
`tests/test_providers.py`, and `tests/test_cli.py`. It activates the
engine-shipped hard `core_drift`
gate on conduct-file paths resolved from routing, compares each committed
managed block with a fresh branch-version render, preserves project-owned
remainder, refuses malformed, duplicate, or partial marker text, and joins the
merge-time mechanical rerun set. Move the complete resolver from inline
`_core` logic into one `squatch/providers.py` function and make both `_core`
and `core_drift` call it; the provider-to-`CLAUDE.md`/`AGENTS.md` mapping must
have one owner and no copied path. Replace
`test_classifier_is_unreachable_from_production_gates` with coverage proving
the gate reaches `hostfiles.classify` and both invokers share the resolver.
Keep `test_rendering_has_no_git_or_commit_effect`; `squatch/hostfiles.py`
retains its exact pure import set. Existing `squatch/merge.py`,
`squatch/providers.py`, `squatch/__main__.py`, `tests/test_gates.py`,
`tests/test_merge.py`, `tests/test_providers.py`, and `tests/test_cli.py` are
measured on-demand exceptions; every other existing fence path is Context.
Every named exception is read from the worktree only when needed and is never
embedded, keeping the base Implement render under headroom.

`migrate-config` depends on `core-renderer` and owns/fences
`squatch/config.py`, `squatch/__main__.py`, `tests/test_config.py`,
`tests/test_cli.py`, and `tests/test_verbs.py`. It adds only the explicit
`migrate-config` verb. The sole supported older schema is version 0: its full
key vocabulary, nesting, value types, defaults, and meanings are exactly
version 1's except for the required top-level integer `schema_version: 0`.
The deterministic 0-to-1 mapping changes only that scalar to integer 1 and
keeps every other key byte-for-byte; it never resolves auth values or changes
host intent. Validate the full candidate through the real loader before one
atomic replace and keep a recoverable adjacent backup. A valid current
version-1 file is a byte-identical no-op. Refuse with no write a missing or
non-integer version, a version below 0 or above 1, an unknown key, or any input
invalid under the version-1 shape after scalar substitution. CLI roots and
tests are measured on-demand exceptions; config and its focused test are
Context.

`phase6-continue-02` depends on both `core-drift-activation` and
`migrate-config`. It authors row 2.

`host-contract-doc` depends on `migrate-config` and owns/fences new
`docs/host-contract.md` and new `tests/test_host_contract.py`. It commits
the section 15 host schema's copyable commented `review`/`merge` example,
seam inventory, report-inbox contract, managed-file ownership rule,
migration/cutover steps, and explicitly excludes foreign process-state
adoption. It has no production-code write and no Context.

`fixture-host-scaffold` depends on both `host-contract-doc` and
`core-drift-activation` and owns/fences new `hosts/fixture/` plus new
`tests/test_fixture_host.py`. The fixture contains a host-root config
profile, miniature deterministic app, replay-runner command, closed scenario
list, bounded version-1 report fixtures, one merge-base regression defect, one
machine-introduced escape scenario, and a scripted agent-CLI provider row
serving Author/Implement/Review at zero model spend. It changes no engine
module and has no embedded Context: sibling-new `docs/host-contract.md` is
excluded at authoring and becomes an ordinary worktree read after its required
`host-contract-doc` dependency merges.

`phase6-continue-03` depends on both `host-contract-doc` and
`fixture-host-scaffold`. It authors row 3.

`bug-gate-grammar` depends on `fixture-host-scaffold` and owns/fences
`squatch/tickets.py`, `squatch/gates.py`, `squatch/stages.py`,
`tests/test_tickets.py`, `tests/test_gates.py`, and new
`tests/test_bug_gate.py`. It adds `kind: bug`, mandatory
`## Regression`, and the branch-head-pass/merge-base-with-`carries`-overlay-
fail hard gate; a missing test at base is never accepted as defect evidence.
Existing `squatch/tickets.py`, `squatch/stages.py`, `tests/test_tickets.py`, and
composition callers are measured on demand; the gate parser and focused
`tests/test_gates.py` are Context.

`report-inbox-triage` depends on `bug-gate-grammar` and owns/fences new
`squatch/inbox.py`, `squatch/box.py`, `squatch/triage.py`,
`squatch/author.py`, `squatch/daemon.py`, `tests/test_box.py`,
`tests/test_triage.py`, `tests/test_author.py`, and new
`tests/test_inbox.py`. It enforces the version-1 report schema,
metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps, copies bounded
evidence into durable Box custody before recording the message, wires the
daemon consumer, and makes sequential triage author `kind: bug` tickets
whose evidence and `## Regression` survive intake. Daemon/Author roots,
`squatch/triage.py`, their large tests, and delimiter-carrying
`tests/test_triage.py` are measured on-demand exceptions; the Box seam and focused
`tests/test_box.py` are Context.

`phase6-continue-04` depends on both `bug-gate-grammar` and
`report-inbox-triage`. It authors row 4.

`escape-column` depends on both `bug-gate-grammar` and
`report-inbox-triage` and owns/fences `squatch/scorecard.py`,
`squatch/git.py`, `tests/test_scorecard.py`, and `tests/test_git.py`. It
adds the squash-trailer read operation and deterministic
bug-to-merged-ticket-or-bounded-range attribution, increments escapes only for
surfaces that passed the attributed merges, and leaves unattributed or foreign
history out. `squatch/git.py` and `tests/test_git.py` may be measured on
demand; scorecard and its test are Context.

`phase6-continue-05` depends on `escape-column`. It authors row 5.

`supervised-merge-hold` is KNOWN-DEEP high/high, depends on
`escape-column`, and owns/fences `squatch/merge.py`,
`squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`,
`squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`,
`tests/test_merge.py`, `tests/test_baseline.py`,
`tests/test_control_cli.py`, `tests/test_cli.py`, `tests/test_drain.py`,
and new `tests/test_supervised_merge_hold.py`. It implements the durable
HELD admission state after merge safety and integration checks but before main
mutation, excludes held stems from dispatch while preserving their worktrees,
releases through identity-bound `confirm` without a cap-rearming keep
signal, rebase/regates against moved main, reconstructs holds on restart, and
never holds the bootstrap self-build. Every existing production root and
broad suite in this fence is a measured on-demand exception; the new focused
test is not Context.

`phase6-continue-06` depends on `supervised-merge-hold`. It authors row 6.

`go-grade-machinery` depends on both `supervised-merge-hold` and
`fixture-host-scaffold` and owns/fences `eval/harness.py`,
`squatch/artifacts.py`, `tests/test_eval_harness.py`, and new
`tests/test_go_grade.py`. It extends the committed harness to at least 50
planted defects under the fixed USD 5.00 cap, runs the harness-local Author
prompt, records the authored tickets and dependency graph in one closed
report, and adds operator-only `--record-go`; production
`specs/author.md` is never used. Existing harness/artifact modules and
`tests/test_eval_harness.py` are Context.

`go-grade-run` depends on `go-grade-machinery`, changes no code, and
owns/fences only `tickets/go-grade-run/review-baseline-report.json`. It
executes the merged harness once through the run lane. The committed report
embeds its mechanically recorded GO-or-NO-GO verdict signal identity; only the
operator may turn an earned result into GO, so NO-GO is a valid self-build
result. Its Context is `eval/harness.py` and `squatch/artifacts.py`.

`phase6-continue-07` depends on both `go-grade-machinery` and
`go-grade-run`. It authors row 7.

`exit-receipt-machinery` depends on `go-grade-run` and owns/fences
`squatch/artifacts.py`, new `eval/host_loop.py`, new
`tests/test_host_loop.py`, and `tests/test_gates.py`. It registers
closed writers for `host-loop-report.json` and `exit-receipt.json`; the
host-loop harness launches supervised `serve` as a subprocess against
`hosts/fixture/`, drives machine-actor confirms through the control inbox,
and records per-member `(member, driven scenario, observable, producing run)`
evidence for at least three machine-ticket merges, the report-to-regression bug
loop, and escape attribution. The machinery never produces terminal artifacts
during its own build. Existing artifact code/tests `squatch/artifacts.py` and
`tests/test_gates.py` are embedded Context; the
directory `hosts/fixture/` is a named measured on-demand worktree read and is
never an embedded Context entry.

`phase6-continue-08` depends on `exit-receipt-machinery`. It authors the
terminal row.

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on
every Phase 6 payload, and is the last row's sole KNOWN-HARD high/high seed. It
authors no successor and owns/fences only
`tickets/phase6-exit/host-loop-report.json`,
`tickets/phase6-exit/exit-receipt.json`, and new
`tests/test_phase6_exit.py`. It runs the registered host-loop producer,
reads the committed GO-grade report and its embedded verdict identity, accepts
GO or NO-GO, proves the three closed host-loop members, writes the receipt
digest, and performs no engine-code edit. Live-host K>=10 and real-host
bug-loop evidence remain operator post-cutover acceptance and are forbidden as
exit inputs. Every fenced path is terminal output or a new focused test, so it
has no Context. It has no successor and no continuation tail is authored.

## Scope out
Do not implement a Phase 6 payload, rename, reorder, split, combine, add, or
omit a payload, invent a Context or on-demand partition, render section 19, or
author a successor after `phase6-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase6_01.py

## Acceptance criteria
- `tests/test_seeded_phase6_01.py` pins row 1 identities, direct edges, tiers, section-20-only citations, exact fences, Context/on-demand partitions, behavior boundaries, and the row-2 continuation edge.
- `tests/test_seeded_phase6_01.py` pins every remaining row's direct edges, exact owner/fence, Context/on-demand partition, behavior contract, and shrinking suffix through `phase6-continue-08`.
- `tests/test_seeded_phase6_01.py` pins KNOWN-DEEP `supervised-merge-hold` high/high and terminal KNOWN-HARD `phase6-exit` high/high custody.
- `tests/test_seeded_phase6_01.py` proves every authored seed renders at max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM` without section 19.
- `tests/test_seeded_phase6_01.py` proves the terminal row contains `phase6-exit` alone, writes only its two receipts and focused proof, and has no successor.

## Verification
```
uv run pytest tests/test_seeded_phase6_01.py -q
uv run pytest -q
```

## Definition of rejected
Reject an invented or incomplete row contract, wrong edge, owner, fence,
Context partition, behavior, tier, section citation, render overflow, or any
successor after the terminal exit.

## Time budget
- expected: 75m
- stuck: 150m
