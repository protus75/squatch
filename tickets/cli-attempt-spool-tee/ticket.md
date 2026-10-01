---
kind: bug
priority: P2
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- cli-prompt-path-reuse

## Context
- squatch/providers.py
- squatch/driver.py
- squatch/llm.py
- tickets/cli-prompt-path-reuse/ticket.md

## Plan contract
- section 6

## Goal
Every `CliClient` call made for a stage attempt writes the adapter's full redacted stdout and the full redacted stderr to two files inside that attempt's spool directory, `<state_dir>/spools/<stem>/<attempt>/`, named with the same `NNN-` call prefix the driver already uses for `NNN-prompt.md` and `NNN-response.md`. Both files land whether the call succeeds, exits non-zero, or raises `ProviderError`. `CliClient` gets the two file paths from the driver through `LLMRequest`, the same way `cli-prompt-path-reuse` carries `prompt_path`, instead of computing a spool location of its own.

## Why
Section 6's attempt-spool contract says the driver tees each call's subprocess stdout/stderr and the agent adapter's JSONL event stream into the per-attempt spool. Today `CliClient.call_resolved` redacts `out`/`err` and then discards both once parsing is done, and the driver's own `Spool` writes only the prompt and the response text. The section 11.2 harvest cuts its tail from whatever the attempt spool directory holds, so without this tee a failed call's most useful diagnostic evidence -- the raw event stream and stderr -- never reaches disk. This is a provider/driver-only fix: harvest already reads whatever the attempt directory holds, so it needs no change once the files are there.

## Scope in
- Add a `path` method to `Spool` in `squatch/driver.py`, `path(self, stem: str, attempt: int, name: str) -> Path`, returning `self.root / stem / str(attempt) / name` with no write; refactor `Spool.write` to call it internally instead of duplicating the join.
- `Driver._run` computes `stdout_path = self._spool.path(stem, attempt, f"{call_seq:03d}-stdout.log")` and `stderr_path = self._spool.path(stem, attempt, f"{call_seq:03d}-stderr.log")` for each call, and passes both when it builds the `LLMRequest`.
- Add required `stdout_path: Path` and `stderr_path: Path` fields to `LLMRequest` in `squatch/llm.py`, ordered directly after `prompt_path`.
- `CliClient.call_resolved` in `squatch/providers.py`, immediately after the existing `out, err = self._redact(out), self._redact(err)` line and before `adapter.parse(out)` runs, writes `self._fs.write(req.stdout_path, out.encode())` and `self._fs.write(req.stderr_path, err.encode())`, so both files are on disk before any `rc != 0` or `ProviderError` branch returns or raises.
- Update every other `LLMRequest` construction site so the suite keeps passing: `tests/test_providers.py`, `tests/test_driver.py`, `tests/test_llm_effect.py`, `tests/test_fixture_host.py`, and `eval/reliability_battery.py`.
- New tests in `tests/test_providers.py` driving one passing `CliClient` call and one call that fails (a non-zero exit, and separately a `ProviderError`-raising case) through a fake process exec, each with a planted secret value in stdout and in stderr, asserting both spooled files land under the attempt directory named from the request's `stdout_path`/`stderr_path` with the secret redacted.

## Scope out
- `squatch/harvest.py` and the section 11.2 tail-cutting logic are unchanged: harvest already reads whatever the attempt spool directory holds.
- No change to `squatch/redact.py`'s redaction rules; this ticket reuses the existing `Redactor` already applied to `out`/`err`.
- No change to adapter parsing (`ClaudeAdapter`, `CodexAdapter`) or the JSONL event vocabulary.
- `CliClient.__init__`'s constructor signature is unchanged beyond what `cli-prompt-path-reuse` already leaves in place.

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
- `LLMRequest` has required `stdout_path: Path` and `stderr_path: Path` fields, checked by `tests/test_driver.py`'s `LLMRequest` construction tests.
- `tests/test_providers.py` proves a successful `CliClient.call_resolved` call writes the full redacted stdout to `req.stdout_path` and the full redacted stderr to `req.stderr_path`.
- `tests/test_providers.py` proves a call that exits non-zero, and separately a call that raises `ProviderError`, still leave both files written on disk before the error propagates.
- `tests/test_providers.py` proves a planted secret value in the fake process's stdout or stderr never appears in either spooled file.
- `pytest tests/test_providers.py tests/test_driver.py tests/test_llm_effect.py tests/test_fixture_host.py -q` exits 0.

## Verification
```
pytest tests/test_providers.py tests/test_driver.py tests/test_llm_effect.py tests/test_fixture_host.py -q
pytest -q
```

## Regression
```
pytest tests/test_providers.py -k attempt_spool_tee -q
```
- carries: tests/test_providers.py

## Definition of rejected
Stop and throw the branch away if wiring the two new paths turns into a rework of `CliClient.__init__`'s signature, a change to `squatch/harvest.py`, or a redesign of `Spool`'s redaction scheme beyond the one new `path` method -- that is a larger refactor than this defect calls for.

## Time budget
- expected: 60m
- stuck: 120m
