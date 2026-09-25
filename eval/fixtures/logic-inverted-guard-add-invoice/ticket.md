---
state: confirmed
source: human
priority: P2
kind: bug
---
# Raise a clear error when the store's parent directory is missing

## Depends on
- none

## Context
- src/ledgerly/storage.py
- tests/test_storage.py

## Goal / Why
Pointing `--store` at a path whose parent directory doesn't exist currently
crashes `add_invoice` with a raw traceback from `open()`; it should raise a
clear `FileNotFoundError` instead.

## Scope in / Scope out
In: add a directory-existence guard to `add_invoice` in storage.py, plus a regression test.
Out: do not change `save_invoices`, `load_invoices`, `delete_invoice`, or the existing duplicate-invoice-id check.

## Scope fence
- src/ledgerly/storage.py
- tests/test_storage.py

## Acceptance criteria
- `add_invoice(path, invoice)` raises `FileNotFoundError` when `path.parent` does not exist.
- `add_invoice(path, invoice)` succeeds normally (no exception) when `path.parent` already exists, exactly as before this change.
- The existing duplicate-invoice-id protection in `add_invoice` is unchanged.
- `pytest tests/test_storage.py` passes.

## Verification
- `pytest tests/test_storage.py`

## Definition of rejected
Throw away the branch if fixing this requires changing the JSON format or touching cli.py.

## Time budget
expected 20m, stuck 60m
