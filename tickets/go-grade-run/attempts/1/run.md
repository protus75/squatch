## Outcome

ok

## Surprises / judgment calls

The live Claude adapter refused its final remaining-cap request before a
model turn. I treat that named cap refusal as a measured partial result only
after at least one scorable review; other infrastructure errors remain
unscored failures.

## Dead ends

The first live invocation reached the adapter's remaining-cap refusal before
the harness could return a report. The corrected capped-partial path resumed
the same journaled run, recorded 42 scored reviews, and wrote the canonical
NO-GO evidence without a further model turn.

## Second problems filed


## Resolved engine/model

Claude CLI / opus served the harness-local Author and Review calls.

## Predicted vs actual

Expected: 75m. Actual: about 15m.
