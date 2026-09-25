---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add a due-soon window report to the CLI

## Depends on
- none

## Context
- src/ledgerly/totals.py
- src/ledgerly/cli.py

## Goal / Why
Finance wants to see invoices due within the next N days from a given
start date, without hand-picking an end date for `due`.

## Scope in / Scope out
In: add `invoices_due_within_days(invoices, start, days)` to totals.py and a `due-soon START DAYS` CLI subcommand that uses it.
Out: do not change the existing `due` command or `invoices_due_between`.

## Scope fence
- src/ledgerly/totals.py
- src/ledgerly/cli.py

## Acceptance criteria
- `invoices_due_within_days(invoices, start, days)` returns every invoice due in the closed range [start, start + days]; an invoice due exactly `days` days after `start` IS included.
- `invoices_due_within_days` never returns invoices due before `start`.
- `ledgerly due-soon 2026-01-01 30` prints one line per matching invoice, same format as `due`.
- The existing `due` command and `invoices_due_between` are unchanged.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away the branch if `due-soon` requires changing `invoices_due_between` or the JSON store format.

## Time budget
expected 20m, stuck 60m
