---
verdict: snag
reviewed_sha: 4db1ef229fc2cc3766964638470a84cfde66cbe3
produced_by_spec_version: '1.0'
produced_at_sha: 4db1ef229fc2cc3766964638470a84cfde66cbe3
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff meets every acceptance criterion and stays inside the fence. One logic defect: when squatch merges its own repo, text in the candidate branch can make the gate raise an engine error instead of producing a failing finding.

## Findings
- correctness_review at squatch/gates.py:41: `_branch_core` reads the untrusted candidate's `squatch/hostfiles.py` and raises `GateError` when that file has no single plain `CORE = <literal>` assignment, or when the value is not a str. An annotated `CORE: str = "..."` or a second `CORE =` line triggers it. `run_gates` re-raises `GateError` on purpose, because it means 'a gate defect is the engine's bug, never a routable finding'. So candidate content becomes an engine crash in `Merge._regate` instead of a hard `core_drift` finding with its paved road. Other malformed input from the same branch already fails closed as a finding through the generic crash path: a `SyntaxError`, a missing file (`FileNotFoundError`), or a non-literal expression (`ValueError` from `literal_eval`). The two `GateError` branches are the odd ones out. I'm fairly sure this is a defect, but I have not traced how merge handles an escaped `GateError`. (paved road: In `_branch_core`, turn a missing, duplicate, non-literal or non-str `CORE` into a failing `core_drift` finding (return it, or raise a non-`GateError` exception the runner already turns into a fail). Keep `GateError` for real gate-protocol defects only. Add a `tests/test_gates.py` case where the candidate uses `CORE: str = '...'` and assert the run fails with a `core_drift` finding instead of raising.)
