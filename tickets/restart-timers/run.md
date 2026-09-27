## Outcome

ok

## Surprises / judgment calls

Managed timers use non-null journal keys, so the new restart fold does not adopt the bootstrap drain's pre-existing unkeyed ceiling records. The existing Runner remains the sole production owner of pre-dispatch reconciliation; the restart composition delegates to that same reconciler and adds no production reap call. Timer ownership lives in a CLI-composed Runner session override so shutdown is awaited before the journal closes. A direct probe confirmed that appending after Journal.close raises `ValueError: write to closed file`.

## Dead ends

The prior pipeline-factory placement was abandoned because the factory can create timer tasks but cannot observe the enclosing Runner session teardown, allowing tasks to outlive the journal.

## Second problems filed


## Resolved engine/model

OpenAI / Codex (GPT-5)

## Predicted vs actual

Expected 75m; actual approximately 20m for this retry.
