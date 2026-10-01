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
- squatch/providers.py
- squatch/driver.py
- squatch/llm.py

## Goal
`CliClient.call_resolved` in `squatch/providers.py` stops writing its own second copy of the prompt file. It takes the prompt path the driver already wrote through `Spool.write` (`squatch/driver.py`), carried on the new `LLMRequest.prompt_path` field (`squatch/llm.py`), and passes that path straight through as the child process's `stdin_path`. `CliClient._seq` and its `spools/<stem-or-surface>/cli/<seq>-<surface>-prompt.md` write are deleted. Every `LLMRequest` construction site and its owning tests are updated to supply `prompt_path` so the suite still passes.

## Why
The attempt spool's prompt file is supposed to be both the record of exactly what was sent and the only channel that delivers the prompt to the agent CLI. `CliClient` instead keeps its own in-memory counter and writes a second copy numbered from 1. That counter resets on every process restart, so a restarted engine calling for the same stem (or, for a ticket-less surface, any call under the same `spools/<surface>/cli/` directory) overwrites the earlier process's `000001-<surface>-prompt.md` -- destroying the one file that recorded what actually reached the prior child's stdin. The driver's attempt-numbered `<attempt>/<call_seq:03d>-prompt.md` is never reused across a restart, so handing the client that path instead removes both the duplicate write and the collision in one change.

## Scope in
- Add a required `prompt_path: Path` field to `LLMRequest` in `squatch/llm.py`, ordered before the defaulted `max_budget_usd` field.
- `squatch/driver.py`'s `_run` passes the path returned by `self._spool.write(...)` as `prompt_path` when it builds the `LLMRequest`.
- `CliClient.call_resolved` in `squatch/providers.py` uses `req.prompt_path` as `stdin_path` and no longer computes or writes its own prompt file; `CliClient._seq` (and its increment) is removed from `__init__` and `call_resolved`.
- Update every other `LLMRequest` construction site so the suite keeps passing: `tests/test_providers.py`, `tests/test_driver.py`, `tests/test_llm_effect.py`, `tests/test_fixture_host.py`, and `eval/reliability_battery.py`.
- A new test in `tests/test_providers.py` proving that two `CliClient` instances (one before and one after a simulated restart) calling for the same stem, each handed its own driver-assigned `prompt_path`, leave two separate, unclobbered prompt files on disk, with neither client writing a file of its own.

## Scope out
- `CliClient.__init__`'s `state_dir`/`fs` parameters and their production call sites (`squatch/stages.py`, `squatch/__main__.py`, `squatch/serve.py`, `eval/harness.py`, `eval/shakeout/providers_group.py`) are unchanged; a now-unread `self._spools`/`self._fs` attribute is left in place rather than reworking that constructor's signature across every caller.
- The separate "prompt-path layout" item the box message refers to is not this ticket; do not fold any further spool-layout redesign in here.
- `squatch/llmeffect.py`'s journaled replay path is unchanged: it already forwards `req` unmodified.

## Scope fence
- squatch/llm.py
- squatch/driver.py
- squatch/providers.py
- tests/test_providers.py
- tests/test_driver.py
- tests/test_llm_effect.py
- tests/test_fixture_host.py
- eval/reliability_battery.py

## Acceptance criteria
- `LLMRequest` has a required `prompt_path: Path` field, checked by `tests/test_driver.py`'s `LLMRequest` construction tests.
- `tests/test_providers.py` proves a `CliClient` call's `stdin_path` passed to the process seam equals the request's `prompt_path` exactly, and that no file is written under any `spools/*/cli/` directory.
- `tests/test_providers.py` proves two `CliClient` instances serving the same stem, each given a distinct attempt-scoped `prompt_path`, never overwrite each other's prompt file.
- `pytest tests/test_providers.py tests/test_driver.py tests/test_llm_effect.py tests/test_fixture_host.py -q` exits 0.

## Verification
```
pytest tests/test_providers.py tests/test_driver.py tests/test_llm_effect.py tests/test_fixture_host.py -q
pytest -q
```

## Regression
```
pytest tests/test_providers.py -k restart -q
```
- carries: tests/test_providers.py

## Definition of rejected
Stop and throw the branch away if removing the duplicate write turns into a rework of `CliClient.__init__`'s signature, the spool directory layout for other surfaces, or the `LLM` protocol beyond the one new `LLMRequest` field -- that is a larger refactor than this defect calls for.

## Time budget
- expected: 45m
- stuck: 90m
