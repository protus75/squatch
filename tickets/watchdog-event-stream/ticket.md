---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-exit

## Context
- squatch/providers.py
- squatch/seams.py
- tests/test_providers.py
- tests/test_seams.py

## Plan contract
- section 20

## Goal
Expose each agent CLI's in-flight event stream through an injectable,
normalized watchdog boundary while preserving the completed-call result.

## Why
The later detector needs progress while a call is still running; parsing only
the returned stdout after process exit cannot distinguish productive work from
a live spiral.

## Scope in
Add `squatch/watchdog.py` and `tests/test_watchdog.py`. The module owns the
closed normalized watchdog event shape and the callback/collector used by the
provider adapters. It is event-stream construction only: there is no detector,
timer, notification, or production activation in this ticket.

Extend `ProcessExec.run` and `SubprocessExec.run` in `squatch/seams.py` with an
optional in-flight event callback over stdout lines. The generic process seam
has no adapter-specific knowledge. While the child is running it delivers each
complete stdout line in arrival order and exactly once, including a final unterminated line at EOF.
It still returns the complete `(rc, out, err)`
capture, accepts the same stdin file, publishes the same process group, and
uses the existing single group-kill-and-wait path for timeout and cancellation.
The callback does not change stderr capture, inherited-stdio calls, spool capture,
cleanup, redaction, or the final adapter parse.

At the provider boundary, let `CliClient.call` accept an optional in-flight
event callback and let each adapter normalize only its own JSONL contract into
the watchdog event shape. Non-JSON chatter is ignored for events but remains
in returned capture. Preserve the terminal parse and cost floor, including a
flat-estimate start event for a provider whose stream reports no dollar cost.
`CliClient` passes the new callback keyword to `ProcessExec.run` only when a consumer was supplied.
When no consumer is supplied, the process call keeps its exact current kwargs,
so an existing fake or wrapper with the current signature never receives the new keyword. Pin that no-consumer call in
`tests/test_providers.py`. Current production construction supplies no callback,
so this boundary stays dormant until `watchdog-activation`.

## Scope out
Do not implement spiral detection, elapsed-time bands, mutation tracking,
notifications, automatic kills, provider failover, or production activation.
Do not add a second subprocess or change the completed provider result.

## Scope fence
- squatch/watchdog.py
- squatch/providers.py
- squatch/seams.py
- tests/test_watchdog.py
- tests/test_providers.py
- tests/test_seams.py

## Acceptance criteria
- `tests/test_seams.py` proves `SubprocessExec` delivers every complete stdout line in order and exactly once, including a final unterminated line, while returned capture, stdin handling, inherited stdio, spawn publication, and group kill-and-wait behavior stay unchanged.
- `tests/test_watchdog.py` and `tests/test_providers.py` prove provider-owned parsing emits normalized adapter events for the supported JSONL tool-call shapes and the no-cost provider's flat-estimate start without changing terminal parsing, redaction, cost, or spool capture.
- `tests/test_providers.py` pins the no-consumer call's exact kwargs and proves the callback keyword is passed only when a consumer was supplied, so an existing fake or wrapper with the current signature remains compatible.
- `tests/test_watchdog.py` proves the event stream is dormant construction: no detector, notification, timeout decision, or production callback is activated.

## Verification
```
uv run pytest tests/test_watchdog.py tests/test_providers.py tests/test_seams.py -q
uv run pytest -q
```

## Definition of rejected
Reject adapter normalization inside the generic process seam, callback delivery
only after process exit, duplicate or dropped lines, changed final capture, an
always-present callback keyword, or any detector or production activation.

## Time budget
- expected: 75m
- stuck: 150m
