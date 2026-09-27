## Outcome
ok

## Surprises / judgment calls
Kept `tests/test_storm_producer.py` out of the notification seed's Context because it is sibling-new at authoring time, while retaining it as that seed's fenced migration target.

## Dead ends
The first authored acceptance criteria omitted their named verification artifacts; ticket lint rejected them, so each criterion now names its proving test. The initial commit included ticket files, so it was safely reshaped to commit only the seed contract test and leave ticket files for engine lift.

## Second problems filed

## Resolved engine/model
OpenAI Codex, model unknown.

## Predicted vs actual
Expected 75m; actual about 25m.
