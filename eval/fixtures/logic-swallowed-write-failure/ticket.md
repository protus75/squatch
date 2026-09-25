---
state: confirmed
source: human
priority: P2
kind: bug
---
# Don't let a write failure look like a successful save

## Depends on
- none

## Context
- src/ledgerly/storage.py
- tests/test_storage.py

## Goal / Why
If `save_invoices` can't write the store (bad path, permissions, disk
full), the caller must find out, not be told the save succeeded.

## Scope in / Scope out
In: harden `save_invoices`'s error handling and add a regression test.
Out: do not change `add_invoice`'s or `delete_invoice`'s call sites, do not switch to atomic/temp-file writes.

## Scope fence
- src/ledgerly/storage.py
- tests/test_storage.py

## Acceptance criteria
- If the underlying file write in `save_invoices` fails, the exception propagates to the caller -- it never returns normally on a failed write.
- `save_invoices` still writes the file successfully for a valid path, unchanged from before.
- A test exercising a failing write (e.g. writing to a directory path) asserts that `save_invoices` raises.

## Verification
- `pytest tests/test_storage.py`

## Definition of rejected
Throw away the branch if it requires changing the store's JSON schema.

## Time budget
expected 20m, stuck 60m
