## Outcome
ok

## Surprises / judgment calls
The repaired seed fixture now treats its byte counts as historical inputs, so the compact activation fits the render headroom without removing existing documentation or typing. The concurrent control owner cancels and awaits dispatch on every control-consumer failure before propagating it.

## Dead ends
The first control-failure regression assertion expected lock release to unlink the lockfile. The lock deliberately persists to preserve flock inode identity, so the test now proves release by reacquiring it.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 25m.
