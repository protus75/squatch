---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-14

## Context
- squatch/journal.py
- squatch/timers.py
- squatch/daemon.py
- squatch/box.py
- squatch/config.py

## Plan contract
- section 20

## Goal
Construct dormant flake detection and the test quarantine ledger.

## Why
The section 20 boundary records a flaky test's report identity before a later release resolves it.

## Scope in
Implement section 20's flake-boundary clarification in new `squatch/flake.py` and `tests/test_flake.py`. The section 11.5 gate re-run law is: "A check that fails then passes on a bare re-run (same workspace, no code change) is a bug signal, not a pass." This boundary is called only after that observation, not after an arbitrary green test.

Accept the named `test_id`, the signature-deduped report `signature`, and the resulting Suggestion Box `box_id` as explicit inputs. The existing `Box.enqueue`/`Box.get` seam supplies report identity; production observation and reporting wiring belong to later activation. Use the existing Journal seam to append one `signal` keyed `flake/<box_id>` with body `{kind: flake_detected, test_id, signature, box_id}`. Fold the journal into a test quarantine ledger: add exactly the named `test_id` entry keyed by `box_id`, changing no other entry. The durable record is the source of truth, never a SHA-held set or an independently edited side-file. Repeated detection for the same report is idempotent. At this boundary, detection writes no release record or release state.

Compose the dormant boundary through a `compose_daemon_flake`-style hook in `squatch/daemon.py`; its direct proof lives in fenced `tests/test_flake.py`. No production composition in `squatch/__main__.py` or `squatch/drain.py` calls or constructs the hook; import reachability through `squatch/daemon.py` is allowed. Existing `tests/test_daemon_composition.py` tests are read-only preservation evidence, with no requested migration.

## Scope out
Do not implement release, production detection/report wiring, gate suppression, or manual resume. Defer section 11.5's `caps.quarantine` bound, cap-crossing halt of further auto-quarantine, and escalation path to later activation: this dormant ledger boundary has no escalation owner in its fence. Do not add config knobs or change shared composition tests.

## Scope fence
- squatch/flake.py
- tests/test_flake.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_flake.py` directly exercises detection after a named failing check passes the same-workspace/no-code-change rerun, carrying its test, signature, and box identities.
- `tests/test_flake.py`: Assert the exact `signal` key `flake/<box_id>` and body `{kind: flake_detected, test_id, signature, box_id}`; detection writes no release record or release state.
- `tests/test_flake.py`: Assert the quarantine-ledger fold adds exactly the named `test_id` entry keyed by `box_id`, changing no other entry; it survives reconstruction and deduplicates the same report without another event.
- Direct hook tests in `tests/test_flake.py` exercise the real component. No production composition in `squatch/__main__.py` or `squatch/drain.py` calls or constructs the hook; import reachability through `squatch/daemon.py` is allowed. Prove call-path dormancy with a source/AST call check that fails if either production root constructs or calls the hook. No SHA-held set substitutes for the test/report ledger identities.

## Verification
```
uv run pytest tests/test_flake.py -q
uv run pytest tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the boundary needs production activation, a SHA-held substitute, an unfenced edit, or an on-demand Context exception for an existing fence path. Report premise_failed naming the missing owner; never widen the fence.

## Time budget
- expected: 75m
- stuck: 150m

