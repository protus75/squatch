## Outcome

premise_failed

## Surprises / judgment calls

The merged `ReviewBaselineReport` records only `verdict_signal_identity`; it
does not carry the GO or NO-GO verdict that `ExitReceipt.go_grade_verdict`
requires. The only GO source is an operator journal signal, which is not a
committed report input.

## Dead ends

Authoring `phase6-exit` would require inventing a verdict, selecting an
unplanned journal lookup despite the pinned empty partition, or changing
section 20 and the receipt schema spelling/digest contract outside this
ticket's scope fence. None is permitted by the ticket.

## Second problems filed


## Resolved engine/model

Unknown.

## Predicted vs actual

Expected 75m; actual approximately 5m to establish the contract conflict.
