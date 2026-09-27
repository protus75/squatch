## Outcome

ok

## Surprises / judgment calls

The plan already specifies this boundary; no plan defect or unfenced edit was needed. The CLI control factory retains one inbox and AdmissionHold per lock-held journal across separate pipeline constructions. The shakeout factory likewise retains the pair per journal. Dispatch pause recovery selects only pause-owned identities, so admission holds remain independent after restart and later pause requests.

Hold identity, lifecycle, and trigger share one durable control_hold event before in-memory mutation; rehydration recovers a crash at that boundary. The queue waits on an asyncio.Event, and the existing control consumer applies matching releases. The optional queue hook preserves construction without the attribute and post-unwind Rework publication.

Both required commands exited 0 on the final code:
- uv run pytest tests/test_mergequeue.py tests/test_merge.py tests/test_daemon_composition.py tests/test_control.py tests/test_rework.py tests/test_shakeout.py -q — 121 passed in 13.21s.
- uv run pytest -q — 1028 passed in 47.86s.

## Dead ends

Replaced separate trigger and hold records during review because a crash between them could lose hold ownership. A single durable record closes that gap; restart tests exercise a crash immediately after its append.

## Second problems filed

None.

## Resolved engine/model

OpenAI / GPT-6 (Codex).

## Predicted vs actual

Expected 75m; actual approximately 10m.
