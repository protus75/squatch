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

## Plan contract
- section 8

## Goal
`tests/test_specs.py` gains a golden test: it renders one fixed fixture `Spec` from fixed fixture `DataBlock` inputs through `Spec.render` and compares the output byte-for-byte against a new snapshot file committed under `tests/golden/`. Any change to `Spec.render`'s output -- whitespace, block ordering, marker framing, or a dropped section -- fails that test until the snapshot is regenerated and committed in the same change. Separately, `test_the_real_plan_resolves_every_numbered_section` is brought in line with its name: either it is changed to resolve every numbered `## N.` heading actually present in `SQUATCH_PLAN.md` and assert each resolved body starts at its own heading and stops before the next one, or it is renamed in place to state plainly that it checks only sections 8 and 13. Production code under `squatch/` is unchanged.

## Why
Plan section 8 states that specs are golden-tested: rendered from fixture inputs and snapshotted. Today's render tests in `tests/test_specs.py` only assert structure by substring (`assert 'name="ticket"' in out`, and similar), so a render change that preserves those substrings -- reordered blocks, altered whitespace, different marker framing, a silently dropped section -- would pass unnoticed. No committed snapshot exists to catch that class of drift. Separately, `test_the_real_plan_resolves_every_numbered_section` only exercises sections 8 and 13 of the real plan, so its name promises coverage it does not deliver; a reader trusting the name would wrongly believe every numbered plan section is exercised against regressions in `resolve_plan_sections`. This is the golden test section 8 already requires, not a speculative addition, and the rename/generalize is a one-line truth-in-naming fix.

The fixture spec module and its existing test file are deliberately not cited here as read-first Context: both `squatch/specs.py` and `tests/test_specs.py` define and exercise the engine's own data-block marker (`DATA_MARKER` in `squatch/specs.py`) as literal bytes in source -- embedding either file's content into a rendered prompt reproduces exactly the marker-collision render refusal that `Spec.render` exists to catch (`squatch/specs.py`'s `test_render_refuses_content_carrying_the_delimiter`-style check). Plan section 8 is the one relevant governing text and is cited through the Plan contract channel instead, which the engine already proves safe to inject (`test_the_real_plan_renders_as_data_without_a_delimiter_collision`). The implementer reads `squatch/specs.py` and `tests/test_specs.py` directly from the worktree.

## Scope in
- One new golden test in `tests/test_specs.py`: a fixed fixture `Spec` (reusing or closely modeled on the existing `GOOD`/`FRONTMATTER`/`BODY` fixtures in that file) rendered through `Spec.render` with fixed `DataBlock` inputs, compared byte-for-byte against a new committed snapshot file.
- The new snapshot file itself, committed under `tests/golden/`.
- `test_the_real_plan_resolves_every_numbered_section` in `tests/test_specs.py`: generalized to check every numbered section, or renamed in place to describe its actual sections-8-and-13 scope.

## Scope out
- `squatch/specs.py` and every other production module under `squatch/` (unchanged).
- Every other existing test in `tests/test_specs.py`.
- `resolve_plan_sections`'s fenced-code-block handling or any other change to the Plan contract resolver's behavior.

## Scope fence
- tests/test_specs.py
- tests/golden/spec_render.txt

## Acceptance criteria
- `uv run pytest tests/test_specs.py -q` exits 0 and includes a new golden test that renders a fixed fixture `Spec` from fixed `DataBlock` inputs and asserts the output equals, byte-for-byte, the committed contents of `tests/golden/spec_render.txt`.
- Editing the fixture spec's template or any fixed input's content in that new test, without updating `tests/golden/spec_render.txt`, makes the golden test fail -- proving the snapshot actually pins the render rather than re-deriving its own expectation.
- `tests/test_specs.py::test_the_real_plan_resolves_every_numbered_section` either (a) discovers every numbered `## N.` heading present in `SQUATCH_PLAN.md`, resolves all of them through `resolve_plan_sections`, and asserts each returned body starts at its own heading line and excludes the next numbered heading's line, or (b) is renamed in place (for example to `test_the_real_plan_resolves_sections_8_and_13`) so its name states only the sections it actually checks; `uv run pytest tests/test_specs.py -q` passes either way and no test in the file promises "every numbered section" coverage it does not have.
- `uv run pytest tests/test_specs.py -q` passes with no change to any other existing test's assertions in that file.

## Verification
```
uv run pytest tests/test_specs.py -q
```

## Definition of rejected
Stop and file an RMA instead of churning if pinning a byte-for-byte snapshot forces a change to `Spec.render`'s actual output (for example to make it deterministic), since this ticket's scope is adding a test and a snapshot, never touching `squatch/specs.py`.

## Time budget
- expected: 30m
- stuck: 75m
