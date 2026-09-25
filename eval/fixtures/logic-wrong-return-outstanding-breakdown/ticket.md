---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add a summary command with a subtotal/tax/total breakdown

## Depends on
- none

## Context
- src/ledgerly/totals.py
- src/ledgerly/cli.py

## Goal / Why
The existing `total` command only prints one number. Finance wants the
subtotal, tax, and grand total across all unpaid invoices in one line.

## Scope in / Scope out
In: add `outstanding_breakdown(invoices) -> tuple[subtotal, tax, total]` to totals.py and a `summary` CLI subcommand that prints all three.
Out: do not change `total_outstanding` or the existing `total` command.

## Scope fence
- src/ledgerly/totals.py
- src/ledgerly/cli.py

## Acceptance criteria
- `outstanding_breakdown(invoices)` returns `(subtotal, tax, total)` where `total == subtotal + tax` for the unpaid invoices.
- `ledgerly summary` prints `Subtotal: X  Tax: Y  Total: Z`, with `Z` equal to `X + Y`.
- Paid invoices are excluded from all three figures, same as `total_outstanding`.
- The existing `total` command's output is unchanged.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away the branch if it requires changing `invoice_total` or `invoice_tax`.

## Time budget
expected 20m, stuck 60m
