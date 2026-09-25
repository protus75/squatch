## Outcome
premise_failed

## Surprises / judgment calls
The landed cap writer owns the `cap_consumed` event body and exposes no way to add the required `rung` field. The ticket explicitly makes inability to carry the rung through that writer a rejected premise.

## Dead ends
Implementing the rung draw would require changing `squatch/caps.py` or duplicating its writer in `squatch/drain.py`. The first is outside the scope fence; the second violates the plan's single-owner rule and the ticket's requirement to use the landed caps writer.

## Second problems filed
None.

## Resolved engine/model
OpenAI / Codex (GPT-5).

## Predicted vs actual
Expected 90m; actual approximately 10m before the premise failure was proven. The untouched base suite passed with 679 tests.
