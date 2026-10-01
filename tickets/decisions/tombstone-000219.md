---
id: tombstone-000219
kind: tombstone
link: spine-harvest
reopen_after_days: 90
message: box-000219-4198a3ec
---
spine-harvest has merged, and both constants now have fixed values in its code: `TAIL_CHARS = 8_000` and `HARVEST_RENDER_CHARS = 24_000` (squatch/harvest.py:15-16). Merged tests check both bounds. tests/test_harvest.py:33 keeps every spool tail within `TAIL_CHARS`, and tests/test_drain_reentry.py:237-249 checks that a harvest render is cut to exactly `HARVEST_RENDER_CHARS` even when the input is twice that size. The prior-attempts render applies the cap at squatch/stages.py:907. So the harvest block a re-entry render can add is limited to 24k characters, well inside the space left under the 320k medium bound that the message cites. The message wants the values written into the seed before the implementer picks them. That concern no longer applies: the seed has run, and the values it produced are fixed and tested. The render-bound concern is also covered for any future ticket, because requisition review measures each authored ticket's Implement render at the tightest `max` bound (decision-000216). The message gives no evidence and comes from `bootstrap-ingest`. Reopen if spine-harvest is regenerated and either constant is dropped, or its cap is no longer enforced in the prior-attempts render, or if a re-entry render is refused `over_bound` because of the harvest block.
