---
state: confirmed
source: human
priority: P2
kind: feature
---
# Sign session tokens with a shared secret

## Depends on
- none

## Context
- src/notely/config.py
- src/notely/auth.py

## Goal / Why
Session tokens should be HMAC-signed with a server-side secret so a
token cannot be forged by guessing the random hex value alone.

## Scope in / Scope out
In: add a `signing_secret` setting loaded from `NOTELY_SIGNING_SECRET`, and thread it through `Settings`.
Out: changing the token format or the login response shape.

## Scope fence
- src/notely/config.py
- config/settings.example.toml

## Acceptance criteria
- `Settings` has a `signing_secret: str` field.
- `load_settings()` reads `NOTELY_SIGNING_SECRET` from the environment.
- When `NOTELY_SIGNING_SECRET` is unset, the service still starts (no `KeyError` or crash).
- `config/settings.example.toml` documents the new `signing_secret` key.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if `signing_secret` is required to be present with no local
fallback story, or if the token format changes.

## Time budget
expected 20m, stuck 60m
