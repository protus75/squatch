## Outcome
ok

## Surprises / judgment calls
`phase3-continue-13` uses the already-existing `tests/test_seeded_phase3_11.py` pattern rather than sibling-new `tests/test_seeded_phase3_12.py`. It embeds the registry's CLI root, `squatch/__main__.py`, but refuses to infer `squatch/drain.py` or an on-demand exception without a plan repair.

## Dead ends
The first `phase3-continue-13` criteria did not repeat the observable test path on two bullets, so ticket lint rejected them; naming `tests/test_seeded_phase3_13.py` directly resolved the lint failure.

## Second problems filed

## Resolved engine/model
OpenAI Codex, GPT-5.

## Predicted vs actual
Expected 75m; actual about 12m.
