---
state: confirmed
source: seed
priority: P1
kind: chore
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- shakeout-merge

## Context
- squatch/providers.py
- squatch/llmeffect.py
- squatch/runner.py
- squatch/drain.py
- tests/test_providers.py
- tests/test_terminal.py

## Plan contract
- section 19

## Goal
The provider shakeout group pins `squatch/providers.py`: an agent-CLI authentication expiry yields an `infra_error` with a harvested finding carrying the class `auth_error` and the re-authentication road for that CLI, drawing the `infra` cap like every failed call -- with the one classification the member needs added to the adapter base, and every prior group's entries re-confirmed before this one appends its own.

## Why
Section 19 names the member "agent-CLI auth expiry yields a classified non-ok naming the re-auth road", and section 13's closed touchpoint list names "re-authenticate an expired agent login" as the operator's only remedy, so the class must be recognizable at the adapter or the operator chases a phantom model failure. Section 6's failure vocabulary places `auth_error` in the closed set whose full classification (`rate_limited`, `quota_exhausted`, `outage`, `unclassified`) and circuit breaker are Phase 3's; this member is the incident that earns the ONE class now (D10), so this group adds exactly the `auth_error` recognition to the adapter base and nothing else of Phase 3's vocabulary. Section 11.1 keeps the terminal honest: a call that ran and failed is metered and draws `infra`. The discriminating observable is the stable `infra_error` terminal plus the CLI-specific class and road in the harvested finding, which a faked unclassified failure cannot carry; human detail never enters the terminal reason or drain parked line.

## Scope in
`squatch/providers.py`: `ProviderError` gains `failure_class`, `auth_error | None` here (the rest of section 6's vocabulary lands with Phase 3), set by the adapter base when the CLI's stream or stderr matches that CLI's authentication-failure signature -- `ClaudeAdapter` and `CodexAdapter` each declare their signature and their re-auth road (`run claude login` / `run codex login` in the operator's shell, never from the engine); the error message carries `auth_error:` and the road, which the existing failure spine harvests into the attempt finding while the terminal reason stays code-only; the `infra` draw is unchanged. A new member module `eval/shakeout/providers_group.py` with `GROUP` = `shakeout-providers` and `MEMBERS`: `auth_expiry_classified` -- the bench's fake process seam answers the implement CLI with that provider's authentication-failure signature and a non-zero exit; observable: the terminal `to: infra_error`, one `cap_consumed` naming `infra`, and `tickets/<stem>/attempts/<n>/harvest.json` holding a finding whose message carries `auth_error` and the re-auth road; expected `infra_error:auth_error`; detail that harvest artifact. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-providers", "eval.shakeout.providers_group")` after the merge group. `tests/test_providers.py` gains the classification pins. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-merge/shakeout-report.json`.

## Scope out
No `rate_limited`, `quota_exhausted`, `outage`, or `unclassified` class, no circuit breaker, no cooldown Timer, no failover, no notify transport (Phase 3-4): the escalation rests in `status` as today. No login performed by the engine. No change to routing, the write grant, the cost floor, or any module but `squatch/providers.py`. No hand-written entry, no edit of a prior group's entries.

## Scope fence
- squatch/providers.py
- eval/shakeout/providers_group.py
- eval/shakeout/registry.py
- tests/test_providers.py

## Acceptance criteria
- In `tests/test_providers.py`, a claude stream whose result carries its authentication-failure signature and a codex stderr carrying its signature each raise `ProviderError` with `failure_class` `auth_error` and a message naming that CLI's login road; a generic non-zero exit raises with `failure_class` null.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-providers --prior tickets/shakeout-merge/shakeout-report.json` exits 0 and writes `tickets/shakeout-providers/shakeout-report.json` whose prior entries are byte-identical to the merge group's report and whose new entry is `shakeout-providers.auth_expiry_classified`, `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-providers/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-providers` lists `squatch/providers.py`, `eval/shakeout/providers_group.py`, `eval/shakeout/registry.py`, and `tests/test_providers.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_providers.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-providers --prior tickets/shakeout-merge/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-providers/shakeout-report.json
git diff --name-only main...shakeout-providers
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the `ProviderError` as landed cannot carry a class without changing how the driver records an `infra_error` reason, if the bench's process seam cannot script a CLI's stream and exit code, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
