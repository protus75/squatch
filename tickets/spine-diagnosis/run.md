## Outcome
ok

## Surprises / judgment calls
The fresh attempt branch no longer contained attempt 0's reviewed code diff, but the journaled review named its still-reachable commit. I restored that scoped implementation, then added direct proofs for every prior review finding. The missing-workspace test now substitutes only the Stages result so the production Pipeline and Diagnoser execute the synthetic path.

## Dead ends
An initial request assertion compared the raw harvest JSON byte-for-byte, but the diagnosis rendering boundary correctly quotes embedded data delimiters. The assertion now compares the deterministically quoted harvest payload.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5 family

## Predicted vs actual
Expected 90m; actual approximately 20m for this re-entry.
