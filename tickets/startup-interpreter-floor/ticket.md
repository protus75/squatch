---
state: draft
source: box:suggestion
priority: P3
kind: chore
agent_tier: medium
agent_effort: medium
---
## Depends on
- none

## Context
- squatch/__main__.py
- tests/test_cli.py
- tests/test_scaffold.py

## Goal
`squatch.__main__.main` refuses to start when the running interpreter is below the D1 floor (Python 3.14), returning the engine-plane refusal exit code with a message and paved road before any verb dispatches. A dedicated test in `tests/test_cli.py` pins this by injecting a lower interpreter version and asserting the refusal. `tests/test_scaffold.py`'s `test_interpreter_meets_floor` comment is corrected to state only what it actually checks.

## Why
`test_interpreter_meets_floor`'s comment cites D1's floor refusal as though it were pinned there, but that test only asserts the version of the process running pytest. Nothing exercises the engine's own startup path, so a regression that let a stale interpreter start the engine would go unnoticed, and the misleading comment suggests coverage that does not exist.

## Scope in
Add an interpreter-floor check to `squatch.__main__.main`, ahead of verb dispatch, that raises the existing `Refusal` when `sys.version_info` is below `(3, 14)`, naming the required floor in its paved road. Add a new test in `tests/test_cli.py` that monkeypatches `sys.version_info` below the floor and asserts `main()` returns `EXIT_REFUSED`. Correct the comment on `tests/test_scaffold.py::test_interpreter_meets_floor` to state it pins only the test-runner's own interpreter version.

## Scope out
Do not change the D1 floor value itself, `pyproject.toml`'s `requires-python`, or the bootstrap conductor's own interpreter handling. Do not add a runtime interpreter check anywhere other than the one `main()` entry seam.

## Scope fence
- squatch/__main__.py
- tests/test_cli.py
- tests/test_scaffold.py

## Acceptance criteria
- `squatch.__main__.main` returns `EXIT_REFUSED` with a `refused:` message and a paved road naming the required interpreter floor, before dispatching to any verb, when `sys.version_info` is below `(3, 14)`. Checked by `python -m pytest tests/test_cli.py -q`.
- A new test in `tests/test_cli.py` monkeypatches `sys.version_info` below the D1 floor and asserts `main()` returns `EXIT_REFUSED`. Checked by `python -m pytest tests/test_cli.py -q`.
- `tests/test_scaffold.py`'s `test_interpreter_meets_floor` comment states only that the assertion pins the test-runner's own interpreter version, and no longer implies it covers engine startup. Checked by the observable artifact `tests/test_scaffold.py`.

## Verification
```
python -m pytest tests/test_cli.py -q
python -m pytest tests/test_scaffold.py -q
```

## Definition of rejected
If `main()` has no single seam every verb passes through before dispatch, so the check cannot be placed once and cover every verb, stop and file the layout gap back to the box rather than scattering the check per-verb.

## Time budget
- expected: 20m
- stuck: 60m
