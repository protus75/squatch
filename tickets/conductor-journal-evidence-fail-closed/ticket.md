---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- bootstrap/conductor.py
- squatch/journal.py

## Goal
`journal_evidence` in `bootstrap/conductor.py` -- regenerated from its `# BEGIN_CONDUCTOR` block in `SQUATCH_PLAN.md` -- stops wrapping every journal segment's every line in `except ValueError: continue` and instead tolerates only a torn final line of the active segment, surfacing any other malformed line as corruption rather than reading it as missing evidence. A new `tests/test_bootstrap_conductor.py` proves the fixed read directly and proves `bootstrap/conductor.py` on disk stays byte-identical to what the edited plan block regenerates.

## Why
Section 6's one law for journal readers tolerates exactly a torn final line of the active segment; every other malformed line is corruption a reader must surface, never skip. `journal_evidence`'s blanket `except ValueError: continue` violates that law for every segment, not just the active one. The verdict gate still never records a false pass, but it misdiagnoses: a corrupt journal reads as "no evidence yet," so an operator waits or reruns a verdict-gated deliverable instead of repairing the journal. `bootstrap/conductor.py` is a generated file (CLAUDE.md, section 1), so the fix belongs in the plan's `# BEGIN_CONDUCTOR` appendix source, with the rendered file regenerated from it, never hand-patched out of sync.

## Scope in
- The `journal_evidence` read loop in the `# BEGIN_CONDUCTOR` block of `SQUATCH_PLAN.md`, regenerated into `bootstrap/conductor.py`.
- A new `tests/test_bootstrap_conductor.py` covering the fixed behavior and the plan/rendered-file consistency.

## Scope out
- Every other function in `bootstrap/conductor.py` (phase/deliverable driving, `claude()`, `adversarial_review`, state persistence).
- `squatch/journal.py` itself, already correct and read-only reference here.
- Any change to the engine's own journal readers (`status`, `audit`), unaffected by this defect.

## Scope fence
- SQUATCH_PLAN.md
- bootstrap/conductor.py
- tests/test_bootstrap_conductor.py

## Acceptance criteria
- `uv run pytest tests/test_bootstrap_conductor.py -q` exits 0, proving `journal_evidence` surfaces corruption instead of returning missing evidence when a malformed line sits in a non-final position of the active segment or anywhere in a non-active segment.
- `uv run pytest tests/test_bootstrap_conductor.py -q` also proves a torn, unterminated final line of the active segment is still tolerated and does not raise.
- `uv run pytest tests/test_bootstrap_conductor.py -q` also proves `bootstrap/conductor.py` on disk is byte-identical to the `# BEGIN_CONDUCTOR`/`# END_CONDUCTOR` block extracted from the edited `SQUATCH_PLAN.md`.

## Verification
```
uv run pytest tests/test_bootstrap_conductor.py -q
```

## Regression
```
uv run pytest tests/test_bootstrap_conductor.py -k corruption -q
```
- carries: tests/test_bootstrap_conductor.py

## Definition of rejected
Stop and file an RMA instead of churning if the only closed fix requires giving the bootstrap conductor a runtime dependency beyond stdlib (for example making `bootstrap/conductor.py` import the `squatch` package), or if no fix exists that keeps `bootstrap/conductor.py` a byte-for-byte regeneration of the plan's `# BEGIN_CONDUCTOR` block.

## Time budget
- expected: 30m
- stuck: 90m
