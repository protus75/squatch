## Outcome
premise_failed

## Surprises / judgment calls
The required deletion makes `tests/test_seeded_phase2.py` fail during collection because its authoring-time fixture unconditionally reads `bootstrap/suggestions.md`. That test is outside the scope fence, so I did not change it or preserve the deleted mailbox through an untracked or runtime-generated shim.

The required module entry successfully ingested 257 bootstrap lines into the parent checkout's instance state directory before this contradiction became visible.

## Dead ends
Implemented and focused-tested the box, registry, harvest hook, status category, drain era pin, and bootstrap ingestion. After deleting `bootstrap/suggestions.md`, `uv run pytest -q` failed during collection with `FileNotFoundError` from `tests/test_seeded_phase2.py:104`. Satisfying the full-suite criterion requires changing that out-of-fence path (or retaining/recreating the file, which contradicts the required deletion), so all code-tree edits were reverted and no commit was made.

## Second problems filed

## Resolved engine/model
OpenAI Codex / gpt-5.6-sol; implement spec 1.1.

## Predicted vs actual
Expected 90m; approximately 25m to the authoring-defect stop.
