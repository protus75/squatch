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
- squatch/stages.py

## Goal
In `squatch/stages.py`, the line starting with `# ---- the Check gates` has exactly two blank lines above it, like every other top-level section break in the module. Today it has three (blank lines at 304-306, banner at line 307). Delete the one extra blank line. No code, comment, or behavior change.

## Why
The module's top-level sections are separated by two blank lines, matching PEP 8. The banner before `# ---- the Check gates` has three, which is whitespace drift left by an earlier diff that no current gate catches. The fix is a one-line deletion with no functional risk.

## Scope in
- Deleting exactly one of the three blank lines immediately above the `# ---- the Check gates` banner line in `squatch/stages.py`, so exactly two remain.

## Scope out
- Any other whitespace, comment, or code change anywhere else in `squatch/stages.py`.
- The banner text itself, or any other section banner in the file.

## Scope fence
- squatch/stages.py

## Acceptance criteria
- The line starting with `# ---- the Check gates` in `squatch/stages.py` has exactly two blank lines immediately above it, and the line above those two is not blank -- checked by the first `Verification` command.
- `squatch/stages.py` imports and its existing test suite still pass -- checked by the second `Verification` command.

## Verification
```
python3 -c "import pathlib;lines=pathlib.Path('squatch/stages.py').read_text().splitlines();idx=next(i for i,l in enumerate(lines) if l.startswith('# ---- the Check gates '));assert lines[idx-1]=='' and lines[idx-2]=='' and lines[idx-3]!='',(idx,lines[idx-3:idx]);print('ok')"
pytest tests/test_stages.py -q
```

## Definition of rejected
Stop and throw the branch away if the three blank lines are not contiguous immediately above the banner, or if removing one line shifts or alters any non-blank line in the file -- this ticket covers one blank-line deletion only, nothing else.

## Time budget
- expected: 5m
- stuck: 15m
