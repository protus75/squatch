## Outcome
ok

## Surprises / judgment calls
The Box recorder callback does not expose origin and `squatch/box.py` is outside the fence, so the daemon producer resolves the just-written durable Box message by occurrence id and supplies its origin at the fenced composition seam. Storm holds are materialized lazily on an exact matching offer, which avoids turning null or non-ticket origins into lifecycle-retaining global holds.

## Dead ends
The first production-root test passed an already constructed scripted pipeline through an extra lambda, bypassing its journal-binding factory call; the test was corrected to use the existing callable factory seam.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual about 35m.
