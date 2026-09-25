---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add a pay command to mark an invoice paid

## Depends on
- none

## Context
- src/ledgerly/storage.py
- src/ledgerly/cli.py

## Goal / Why
There's no way to mark an invoice paid short of hand-editing the JSON
store; users need a `pay INVOICE_ID` command.

## Scope in / Scope out
In: add `mark_paid(path, invoice_id) -> bool` to storage.py and a `pay` CLI subcommand wired to it.
Out: do not change the `Invoice`/`LineItem` schema, do not add partial-payment or unpaid-reversal support.

## Scope fence
- src/ledgerly/storage.py
- src/ledgerly/cli.py
- tests/test_storage.py

## Acceptance criteria
- `mark_paid(path, invoice_id)` sets the matching invoice's status to `InvoiceStatus.PAID` and persists it, returning True.
- `mark_paid(path, invoice_id)` returns False and leaves the store unchanged when no invoice with that id exists.
- `ledgerly pay INV-1` exits 0 and prints `INV-1 marked paid` on success.
- `ledgerly pay does-not-exist` exits 1 and prints an error to stderr.

## Verification
- `pytest tests/test_storage.py`

## Definition of rejected
Throw away the branch if it requires changing how invoices are loaded/saved.

## Time budget
expected 20m, stuck 60m
