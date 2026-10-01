---
kind: chore
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

## Plan contract
- section 0
- section 1

## Goal
SQUATCH_PLAN.md's Phase 0 prompt 2 (the project-scaffold prompt) tells the builder to version-track `uv.lock` and never gitignore it, instead of telling it to commit the file itself. No other prompt text changes, and neither generated file changes: `bootstrap/conductor.py` parses the Phase 0 playbook live from SQUATCH_PLAN.md at run time rather than carrying a copied checklist, so regenerating `bootstrap/conductor.py` and `README.md` from the plan's sentinel blocks still matches what's committed.

## Why
The conductor commits per deliverable by running `git add -A` over whatever the builder context left in the uncommitted tree -- the conductor decides what lands in the commit, not the builder. A prompt that tells the builder to commit `uv.lock` itself asks for a side commit the conductor's own commit step never reviews, so that change is hidden from the one diff the conductor's adversarial review context reads before advancing. The plan is the seed for this prompt text, so leaving the ambiguous wording in place means every future re-bootstrap from this document asks a builder to do the same wrong thing again; fixing it in the plan is the only fix that does not recur.

## Scope in
- `SQUATCH_PLAN.md`: section 0's Phase 0 prompt 2 ("Project scaffold") uv.lock instruction, reworded from "Commit uv.lock" to an instruction to track it and never gitignore it.

## Scope out
- Every other Phase 0 (or Phase 1) prompt and its wording, the conductor's `git add -A` per-deliverable commit flow, and any other mention of a version-tracked file in the plan -- all untouched.
- `README.md` and `bootstrap/conductor.py` themselves -- the Phase 0 prompt playbook is parsed live from SQUATCH_PLAN.md at run time (`bootstrap/conductor.py`'s own docstring: "the single source -- no copied checklist"), never duplicated into either generated file, so neither needs editing; verification instead confirms neither has drifted from the plan's sentinel blocks.

## Scope fence
- SQUATCH_PLAN.md

## Acceptance criteria
- SQUATCH_PLAN.md's Phase 0 prompt 2 no longer tells the builder to commit `uv.lock`; it instructs the builder to track `uv.lock` and never gitignore it (checked by `grep -n "track uv.lock" SQUATCH_PLAN.md`).
- Regenerating `bootstrap/conductor.py` and `README.md` from SQUATCH_PLAN.md's `BEGIN_CONDUCTOR` / `BEGIN_README` sentinel blocks still matches the committed files byte-for-byte (checked by the python3 extractor-diff command below).
- `tests/test_scaffold.py` still passes (checked by `uv run pytest tests/test_scaffold.py -q`).

## Verification
```
grep -n "track uv.lock" SQUATCH_PLAN.md
python3 -c "import re,pathlib; plan = pathlib.Path('SQUATCH_PLAN.md').read_text(); cond = re.search(r'# BEGIN_CONDUCTOR\n(.*?)\n# END_CONDUCTOR', plan, re.S).group(1) + '\n'; readme = re.search(r'# BEGIN_README\n(.*?)\n# END_README', plan, re.S).group(1) + '\n'; assert cond == pathlib.Path('bootstrap/conductor.py').read_text(); assert readme == pathlib.Path('README.md').read_text()"
uv run pytest tests/test_scaffold.py -q
```

## Definition of rejected
Stop and throw the branch away if making the instruction unambiguous turns out to require touching the `BEGIN_CONDUCTOR` or `BEGIN_README` sentinel blocks, the conductor's gate or commit logic, or any other phase's prompt -- that is wider than this ticket's scope and belongs in a follow-up filed to the Suggestion Box.

## Time budget
- expected: 15m
- stuck: 45m
