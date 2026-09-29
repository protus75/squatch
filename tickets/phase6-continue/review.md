---
verdict: snag
reviewed_sha: e645719a01e81a964fff4309e17537a086185e58
produced_by_spec_version: '1.0'
produced_at_sha: e645719a01e81a964fff4309e17537a086185e58
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The row-1 tickets and the row-1 pins are correct, and the render test is sound. The remaining-row pins do not hold direct edges exactly. Also, the pinned `phase6-continue-02` row contract leaves out behavior clauses that the commissioning ticket requires for `exit-receipt-machinery` and `phase6-exit`.

## Findings
- correctness_review at tests/test_seeded_phase6_01.py:226: Acceptance criterion 2 requires every remaining row's exact direct edges to be pinned. The test only checks that some text containing 'depends' follows the stem and that each dependency name appears somewhere in the whole `phase6-continue-02` Scope in. Every payload name appears in that text anyway, so these checks always pass. For example, the test would still pass if `escape-column` lost its `report-inbox-triage` edge, if `go-grade-machinery` lost `fixture-host-scaffold`, or if `phase6-exit` depended on the wrong row. The continuation checks at lines 245-249 have the same problem: they only look for parent names anywhere in the scope. (paved road: For each stem, capture the clause from `` `<stem>` ...depends on `` up to the next comma or clause boundary (the same way the owns/fences clause is captured). Extract the backticked stems from that clause and assert they equal the expected dependency tuple exactly. Do the same for each `phase6-continue-0N` edge and for `phase6-exit`.)
- correctness_review at tests/test_seeded_phase6_01.py:149: Row contracts are incomplete. The commissioning ticket requires `exit-receipt-machinery` to launch supervised `serve` as a subprocess against `hosts/fixture/` and to record per-member `(member, driven scenario, observable, producing run)` evidence. It requires `phase6-exit` to run the registered host-loop producer and to forbid live-host K>=10 and real-host bug-loop evidence as exit inputs. `tickets/phase6-continue-02/ticket.md` (inside this ticket's `tickets` fence) leaves all of these out. The behavior tuples in REMAINING do not pin them, so the test accepts an incomplete row contract, which the Definition of rejected names explicitly. (paved road: Add the missing clauses to `tickets/phase6-continue-02/ticket.md`: the subprocess against `hosts/fixture/`, the per-member evidence tuple, running the registered host-loop producer, and the ban on live-host and real-host evidence as exit inputs. Add matching phrases to the `exit-receipt-machinery` and `phase6-exit` behavior tuples so the test enforces them.)
