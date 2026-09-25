## Outcome
ok

## Surprises / judgment calls
The prior implementation was present as an earlier commit but not on this attempt's branch, so it was reapplied before fixing the carried review finding. Policy and lint now run before any ticket-plane write; a failed commit is unstaged and its ticket directory is moved out of the ticket plane through the filesystem seam so the item remains retryable.

## Dead ends


## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 90m; actual about 15m on this re-entry.
