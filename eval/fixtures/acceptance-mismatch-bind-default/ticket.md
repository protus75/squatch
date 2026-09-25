---
state: confirmed
source: human
priority: P2
kind: feature
---
# Make the bind host configurable

## Depends on
- none

## Context
- src/notely/config.py
- config/settings.example.toml

## Goal / Why
Operators need to override the bind address per deployment (e.g. behind
a reverse proxy on a private interface), while a fresh local checkout
should stay safe and listen on loopback only.

## Scope in / Scope out
In: read `NOTELY_HOST` from the environment in `load_settings()`, defaulting to `127.0.0.1` when unset.
Out: changing the port default or the settings file format.

## Scope fence
- src/notely/config.py
- config/settings.example.toml

## Acceptance criteria
- `load_settings()` reads `NOTELY_HOST` from the environment.
- When `NOTELY_HOST` is unset, `Settings.host` defaults to `"127.0.0.1"`.
- `Settings.port`'s default is unchanged at `8080`.
- `config/settings.example.toml` shows `host = "127.0.0.1"` as the example value.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if the default bind address becomes anything other than
`127.0.0.1`, or if the port default changes.

## Time budget
expected 20m, stuck 60m
