## Outcome

ok

## Surprises / judgment calls

The branch did not contain the prior implementation; rebuilt the fenced control inbox and retained decision-first replay semantics. Invalid and conflicting files are journaled as refusal outcomes and removed without blocking later requests.

## Dead ends

The first crash-publication fixture used the publisher's own temporary filename, so publication correctly replaced it. The fixture was changed to an unrelated interrupted atomic-write temporary file.

## Second problems filed


## Resolved engine/model

Unknown.

## Predicted vs actual

Expected 75m; actual approximately 25m.
