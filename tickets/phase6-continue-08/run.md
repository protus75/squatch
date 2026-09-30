## Outcome

ok

## Surprises / judgment calls

`eval/host_loop.py::run()` returns a validated model and does not write an
artifact. The terminal seed therefore assigns serialization to the exit and
describes `KNOWN_ARTIFACTS` as the ordinary-lane validator registry.

## Dead ends

The initial seeded contract test used wrapped-string assertions that did not
match the ticket's prose wrapping; the assertions were made semantic instead.

## Second problems filed



## Resolved engine/model

OpenAI Codex (GPT-5).

## Predicted vs actual

Expected 75m; actual approximately 14m.
