---
kind: bug
priority: P1
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- tests/test_providers.py
- config.yaml

## Goal
In `tests/test_providers.py`, `test_checkout_config_routes_review_author_implement_at_every_tier` and `test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting` check only the authored shape of the checkout `config.yaml`, never its operator-owned model values. Both tests keep asserting: providers `claude` and `codex` exist; `review`, `author`, and `implement` each resolve at every tier; `implement` resolves to a `cli`-kind provider; `author` and `review` resolve to `claude`; and every resolved route carries a non-empty model. Both tests drop: the assert that `author.model`/`implement.model` equals that provider's `models_by_tier` entry for the tier, the assert that `review.model == models_by_tier.max`, and the per-row assert that only the `review` row pins a model while every other row's model is `None`. `squatch/providers.py`, `squatch/config.py`, and `config.yaml` are untouched, and the full `tests/test_providers.py` suite passes against the current checkout `config.yaml`.

## Why
Model ids, pins, and per-tier choices in the checkout `config.yaml` belong to the operator, not the engine, but these two tests encode today's values as invariants. The live config already breaks one: its high-tier review row pins `sonnet` (`config.yaml:43`) while `claude.models_by_tier.max` is `opus` (`config.yaml:22`), so `review.model == models_by_tier.max` fails for `tier=high` right now. A routine operator tuning edit should never turn the engine suite red. Inheritance and pin-precedence are engine behavior, and are already proven against the in-file `CONFIG` fixture by `test_candidate_without_a_model_inherits_models_by_tier` and `test_pinned_model_overrides_models_by_tier` -- checking the live values on top of that only blocks legitimate config edits.

## Scope in
- Rewriting `test_checkout_config_routes_review_author_implement_at_every_tier` in `tests/test_providers.py` to drop its `author.model`/`implement.model`/`review.model` value-equality asserts and keep its shape asserts (provider identity, provider kind, non-empty model).
- Rewriting `test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting` in `tests/test_providers.py` to drop the per-row "only review pins a model" assert.

## Scope out
- `squatch/providers.py`, `squatch/config.py`, and `config.yaml` (production code and the operator's config stay as they are).
- `test_checkout_config_yaml_loads_and_builds_a_registry`, `test_candidate_without_a_model_inherits_models_by_tier`, and `test_pinned_model_overrides_models_by_tier` (already fixture-scoped, left unchanged).

## Scope fence
- tests/test_providers.py

## Acceptance criteria
- `test_checkout_config_routes_review_author_implement_at_every_tier` still asserts, at every tier, that `implement` is a `cli`-kind provider, `author` and `review` are `claude`, and `review`/`author`/`implement` each resolve to a non-empty model, and no longer asserts `author.model`, `implement.model`, or `review.model` against any `models_by_tier` value, checked by `pytest tests/test_providers.py -k test_checkout_config_routes_review_author_implement_at_every_tier -q`.
- `test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting` no longer asserts that every non-review row's `candidate.model` is `None`, checked by `pytest tests/test_providers.py -k test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting -q`.
- The full `tests/test_providers.py` suite passes against the current checkout `config.yaml`, checked by `pytest tests/test_providers.py -q`.
- `squatch/providers.py`, `squatch/config.py`, and `config.yaml` are byte-unchanged, checked by `git diff --quiet -- squatch/providers.py squatch/config.py config.yaml`.

## Verification
```
pytest tests/test_providers.py -k test_checkout_config_routes_review_author_implement_at_every_tier -q
pytest tests/test_providers.py -k test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting -q
pytest tests/test_providers.py -q
git diff --quiet -- squatch/providers.py squatch/config.py config.yaml
```

## Regression
```
pytest tests/test_providers.py -k "test_checkout_config_routes_review_author_implement_at_every_tier or test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting" -q
```
- carries: tests/test_providers.py

## Definition of rejected
Stop and throw the branch away if making these two tests pass requires touching `squatch/providers.py`, `squatch/config.py`, or `config.yaml`, or requires moving any of the dropped value-equality checks into a new test against the live checkout config rather than deleting them outright.

## Time budget
- expected: 20m
- stuck: 60m
