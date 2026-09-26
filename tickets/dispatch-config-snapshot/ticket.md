---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- dispatch-admission-boundary

## Context
- squatch/config.py

## Plan contract
- section 20

## Goal
Capture an isolated config value for each admitted dispatch.

## Why
A config edit between offers must affect the next dispatch without changing the configuration already handed to running work.

## Scope in
Add a snapshot constructor in `squatch/config.py` that takes the validated `Config` returned by the unchanged `load`/`parse` functions and produces a deeply detached per-dispatch Config value. Wire it into the dormant admission boundary in `squatch/daemon.py` through an injected zero-argument config supplier returning Config: call that supplier once per accepted offer and construct its snapshot before starting work. A busy refusal does not call the supplier. The admitted work callback receives that captured value for its whole run. Tests call the snapshot constructor directly and exercise the real admission boundary with a controlled supplier, without introducing another filesystem loader. The dependency supplies daemon.py and its admission test; they are not Context because they do not yet exist when this seed is authored.

```yaml
ownership:
  dispatch-config-snapshot:
    owns:
      - tests/test_daemon_config.py
    hooks:
      - squatch/daemon.py
      - squatch/config.py
      - tests/test_daemon_admission.py
```

The predecessor test is fenced to migrate callback signatures and construction fixtures when the config supplier and captured callback argument are added. Preserve all single-flight, busy-refusal, completion, exception, and cancellation assertions.

## Scope out
Do not change Config fields, defaults, load/parse signatures or validation behavior. Do not freeze or otherwise alter the existing Config model globally. No config knobs, polling, config watcher, production caller changes, scheduler activation, CLI verbs, or control behavior. Preserve the existing production import closure: config must not import daemon, scheduler, or watcher. New tests contain no global dormancy/CLI-absence assertion that later activation would have to edit outside its registry fence.

## Scope fence
- squatch/daemon.py
- squatch/config.py
- tests/test_daemon_admission.py
- tests/test_daemon_config.py

## Acceptance criteria
- `tests/test_daemon_config.py` calls the snapshot constructor with Config values returned by `parse` and `load`. Mutating the source's nested provider limits, routing candidates, and review lists/dicts cannot change the captured values; mutating the captured value cannot change the source. Detachment includes nested mutable objects, not just a top-level copy.
- `tests/test_daemon_config.py` drives real admission with a blocked first callback: its snapshot remains unchanged when the supplier's Config changes, the next accepted dispatch sees the new values, and each accepted dispatch calls the supplier exactly once. A busy offer neither reads config nor creates work. The callback receives the same captured value throughout that dispatch.
- `tests/test_daemon_config.py` proves supplier or snapshot-construction failure starts no work, surfaces the original error, and leaves admission able to accept a later valid offer. `tests/test_daemon_admission.py` retains all admission invariants while migrating only the config-supplier/callback fixtures needed by the new signature.
- `uv run pytest tests/test_daemon_config.py tests/test_daemon_admission.py tests/test_config.py tests/test_scheduler.py -q` exits 0. Existing config validation and scheduler dormancy assertions remain valid. Record a discriminating, construction-only scan of the production-root import closure showing daemon remains unreachable; do not install a permanent global absence assertion in the dispatch tests.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_daemon_config.py tests/test_daemon_admission.py tests/test_config.py tests/test_scheduler.py -q
uv run pytest -q
```

## Definition of rejected
Stop if snapshotting requires changing existing Config validation, editing a production caller, or modifying an unfenced predecessor test. Do not activate the daemon to demonstrate this dormant boundary.

## Time budget
- expected: 75m
- stuck: 150m
