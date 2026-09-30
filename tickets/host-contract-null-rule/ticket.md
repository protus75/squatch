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
- squatch/config.py
- docs/host-contract.md

## Goal
The Configuration section of `docs/host-contract.md` states the loader's actual defaulting rule: an explicit `null` is refused for every config key, including the optional keys that carry no shipped default (`notify`, `report_inbox`, a provider's `auth`, `est_cost_per_call_usd`, a routing candidate's `model`). The section names `notify` as the worked example: omitting the key is how an operator leaves it unset or turns it off, and writing `notify: null` is a load refusal, not "off".

## Why
`_nulls` in `squatch/config.py` refuses a `None` at any depth in the parsed config, and the `notify` validator's own refusal message already tells the operator to omit the key to disable it. `docs/host-contract.md` never states this rule at all, so an operator reading only the published contract can reasonably write `notify: null` expecting "off" and discover the refusal only at load time. The loader already fails closed with a paved road; the gap is that the contract doesn't document that road. This is a documentation-only fix: the loader behavior and its example block are correct and unchanged.

## Scope in
- Adding a stated null-refusal rule to the Configuration section of `docs/host-contract.md`.
- Naming `notify` as the worked example: `notify: null` is refused at load; omitting `notify` disables it.
- Stating that the same omit-to-unset rule applies uniformly, including to optional keys with no shipped default.

## Scope out
- Any change to `squatch/config.py`, its validators, or its error messages.
- Any change to the copyable config example block's content or keys.
- Any change to SQUATCH_PLAN.md section 15.

## Scope fence
- docs/host-contract.md

## Acceptance criteria
- `docs/host-contract.md`'s Configuration section states that an explicit `null` is refused for every config key, including optional keys with no shipped default: checked by `grep -n "null" docs/host-contract.md` returning at least one match.
- The section states that omitting a key is how an operator leaves it unset or turns it off, using `notify` as the example: checked by `grep -n "notify" docs/host-contract.md` showing the omit-to-disable statement.
- `squatch/config.py` is unchanged by this ticket: checked by `git diff --stat squatch/config.py` producing no output.

## Verification
```
grep -n null docs/host-contract.md
grep -n notify docs/host-contract.md
git diff --stat squatch/config.py
```

## Definition of rejected
If `docs/host-contract.md` has no Configuration section to extend, or the described null-refusal behavior does not match `squatch/config.py`'s actual `_nulls` check on inspection, stop without editing the doc and file the discrepancy back to the Suggestion Box rather than guessing at the rule.

## Time budget
- expected: 15m
- stuck: 30m
