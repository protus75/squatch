---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- watchdog-event-stream
- notify-transport

## Context
- squatch/watchdog.py
- squatch/providers.py
- tests/test_watchdog.py
- tests/test_providers.py

## Plan contract
- section 20

## Goal
Construct the dormant deterministic spend-without-progress detector.

## Why
The event stream exists; construction must prove progress accounting before production activation.

## Scope in
Implement only the detector in squatch/watchdog.py and direct tests in tests/test_watchdog.py.
Preserve WatchdogEvent, WatchdogCallback, and EventCollector contracts. Consume the
normalized event stream plus separate injected declared-output mutation observations:
WatchdogEvent has no path. A mutation resets accumulated spend only for a path
matching a ticket Scope fence prefix (path-component boundaries, not a lexical
near-prefix). Use the injectable clock; take expected/stuck budgets, scope fence,
and serving-row per-call cost basis as explicit inputs.

All accounting is USD: the cost basis is an injected USD float; metered spend sums
WatchdogEvent.usd. Retain token observations but never compare tokens with USD and
never invent a token-to-USD conversion. Accept an explicit flat USD estimate input
for a provider without metered usage, mechanically identified by an injected
per-provider metered-usage flag. Charge it once per invocation, not once per tool:
a normalized start event already carrying that estimate is not charged twice.
A tokens-only event stream uses that flat estimate, never token counts as cost.
Spend strictly greater than 3 times the serving-row per-call cost basis since the
last declared-output mutation is the sole spiral signal; equality does not trip.

Accept separate injected provider-cap wait intervals and exclude their elapsed
time from time-region accounting. They are neither a new WatchdogEvent kind nor a
spiral signal. watchdog-activation supplies those observations later.
Below expected * 1.5 is healthy; from expected * 1.5 to strictly below stuck is the
soft band. The soft band is empty when expected * 1.5 >= stuck; stuck wins at
elapsed >= stuck. Pin expected=stuck=10 at elapsed 9, 10, 15 and expected=8,
stuck=10 at elapsed 9, 10, 12, as well as a nonempty soft band expected=10,
stuck=20 at elapsed 14, 15, 19, 20 (all values in the same time unit).
Only a soft-band signal emits a soft-trip decision, once per ticket/run_seq;
a fresh run may trip again. Healthy observations do not page. Stuck selects the
existing hard-timeout outcome; this construction does not abort or notify.

Keep construction dormant: retain the executable predecessor
 test_watchdog_construction_has_no_production_callback_consumer in tests/test_watchdog.py.
Adding detector methods must not install a production callback or import a
production root. The later watchdog-activation owns migration of that assertion.
Use deterministic event/mutation/clock fixtures, not live providers or wall time.

## Scope out
No production binding, notifications, new signal shapes, provider changes, config
knobs, heartbeat changes, or automatic kill on a soft spiral. Do not migrate
production dormancy here.

## Scope fence
- squatch/watchdog.py
- tests/test_watchdog.py

## Acceptance criteria
- `tests/test_watchdog.py` proves strict >3x USD accounting, mutation reset only inside component-bounded fences, retained token observations, the tokens-only flat-estimate case, and no double charge for the normalized start event.
- `tests/test_watchdog.py` drives the injected clock and cap-wait observations across every named healthy/soft/stuck boundary, including both empty-soft-band cases; stuck takes precedence.
- `tests/test_watchdog.py` proves one soft decision per ticket/run_seq and a new decision for a new run, with no notification or abort; the predecessor production-callback dormancy test remains executable and green.
- `tests/test_providers.py` remains green unchanged, preserving normalization and optional callback behavior.

## Verification
```
uv run pytest tests/test_watchdog.py tests/test_providers.py -q
uv run pytest -q
```

## Definition of rejected
Reject a no-op detector, token/USD comparison, lexical near-prefix reset, double estimate charge, production activation, or a soft-trip auto-kill.

## Time budget
- expected: 75m
- stuck: 150m
