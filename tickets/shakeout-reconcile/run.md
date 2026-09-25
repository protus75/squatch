## Outcome
ok
## Surprises / judgment calls
The driver converts model-call exceptions into `infra_error`, so the process-death fixture faults the production pipeline immediately after the fake implementer writes `run.md`; this reaches Runner's fault boundary and leaves the real worktree and `running` transition intact.
## Dead ends
The first fixture acceptance-criterion wording did not satisfy ticket lint's exact Verification-command reference rule; it was replaced with the argv-normalized command spelling.
## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5
## Predicted vs actual
45m / about 18m
