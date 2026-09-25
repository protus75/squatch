---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add a quick invoice-building helper

## Depends on
- none

## Context
- src/ledgerly/models.py

## Goal / Why
Callers building invoices ad hoc construct `LineItem` objects by hand every
time, and always want a flat "Service fee" line included. One factory
function should do both.

## Scope in / Scope out
In: add `build_invoice(invoice_id, client, due_date, extra_items=None)` to models.py.
Out: do not change the `Invoice`/`LineItem` dataclass fields, do not touch storage.py or cli.py.

## Scope fence
- src/ledgerly/models.py
- tests/test_models.py

## Acceptance criteria
- `build_invoice("INV-1", "Acme", due)` returns an Invoice whose `.items` is exactly one LineItem: "Service fee", quantity 1, unit_price 25.0.
- Calling `build_invoice` a second time with different arguments and no `extra_items` again returns exactly one "Service fee" line item, not two or more.
- Passing `extra_items=[("Consulting", 2, 100.0)]` returns an invoice with both the service fee and the consulting line item.
- `Invoice` and `LineItem` are otherwise unchanged.

## Verification
- `pytest tests/test_models.py`

## Definition of rejected
Throw away the branch if the helper needs to change `Invoice.to_dict`/`from_dict`.

## Time budget
expected 20m, stuck 60m
