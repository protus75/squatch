---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- status-projection
- baseline-binding-reader

## Context
- squatch/retro.py
- tests/test_retro.py

## Plan contract
- section 20

## Goal
Close the manual retrospective and mechanical doctor operator boundary.

## Why
Operators need a governed forced retrospective and a provider-free diagnosis
surface before the terminal Phase 5 evidence read.

## Scope in
Add the lock-held `retro` verb as the manual forced path over the current
window. It composes the shared provider/cooldown payload, Driver,
`specs/retro.md`, Git/Effects, Box, and `Retro.run("manual", forced=True)`
path used by the drain hook; it creates neither a second model client nor a
second report writer. With no merge after the latest completed report it prints
exactly `retro: no merge since the latest completed report` and exits 0 without
a model call or write. A successful run prints exactly `retro: committed
tickets/retro/<next-zero-padded-seq>.md` and exits 0. A suppressed or failed
selected run prints exactly `retro: no report committed; inspect status and the
Suggestion Box` and exits 1. Lock, config, Git, construction, and journal
failures retain refusal rendering and exit 2.

Add provider-free `doctor` in new `squatch/doctor.py`. It reports exactly the
ordered checks `venv`, `git`, `config`, `lock`, and `journal`: the running
interpreter is the checkout `.venv`; git resolves and answers through the
process seam; config loads through its schema; the advisory lock is available
or has a parseable live-holder record; and all active and rolled journal
records are readable. It reads only interpreter/environment, Git version,
config, lock record/state, and journal and writes no filesystem, journal,
ticket, Box, Git-repository, provider, or model state. Render exactly one
`doctor: ok|failed` summary followed by ordered `PASS|FAIL <name>: <bounded
detail>` lines. Run every check, convert exceptions to bounded details without
a traceback, exit 0 only when all pass, and otherwise exit 2.

The fenced measured on-demand inspection exceptions are `squatch/__main__.py`
(24624 bytes), `tests/test_cli.py` (19367 bytes), and `tests/test_verbs.py`
(9901 bytes). These are synthetic authoring-time sizes, never live-size
assertions. New `tests/test_doctor.py` owns doctor behavior.

## Scope out
Do not make doctor a retro-window or model view, add a second production Retro
path, write from doctor, or alter unrelated CLI behavior.

## Scope fence
- squatch/doctor.py
- tests/test_doctor.py
- squatch/retro.py
- squatch/__main__.py
- tests/test_retro.py
- tests/test_cli.py
- tests/test_verbs.py

## Acceptance criteria
- `tests/test_doctor.py` proves the five ordered injected-seam checks, bounded exception handling, read-only boundary, exact rendering, and 0/2 exits.
- `tests/test_retro.py` proves manual retro no-merge, successful committed-report, and selected failure behavior through the governed Retro path.
- `tests/test_cli.py` proves lock and refusal rendering, parser registration, exact operator output, and exit classes for both verbs.
- `tests/test_verbs.py` preserves the CLI verb surface while proving the manual `retro` and provider-free `doctor` dispatch contracts.

## Verification
```
uv run pytest tests/test_doctor.py tests/test_retro.py tests/test_cli.py tests/test_verbs.py -q
uv run pytest -q
```

## Definition of rejected
Reject a second model or report path, a doctor write or provider call, unordered
or partial doctor output, or retro output/exit behavior outside the contract.

## Time budget
- expected: 75m
- stuck: 150m
