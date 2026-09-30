---
id: decision-000012
kind: decision
link: box-000012-d1dbe96d
reopen_after_days: 90
message: box-000012-d1dbe96d
---
No action needed. The failure described is already loud and fails closed, and the proposed check would not remove the orphan. `Effects.run` (squatch/effects.py:58-63) appends `effect_intent`, runs the action, then appends `effect_completion`. `Journal.append` serializes with `json.dumps(..., allow_nan=False)` (squatch/journal.py:134) before any bytes are written. A result that cannot be encoded as JSON therefore raises at the call site, no partial line reaches the segment, and the intent is left without a completion, which reconcile-on-entry then reports as a stranded key. That is the designed orphan path, and it surfaces the error rather than hiding it. A body-model check at the write seam would still run after the action has executed, so it could only rename the exception. It could not prevent the orphan. By the message's own account, results are JSON by contract and the case is acceptable in v1. Adding a validation layer with no incident behind it is speculative work, which the anti-bloat law rules out. The open ticket `effects-completion-result-corruption` covers a different defect: on the read side, a completion that is missing its `result` field. It does not duplicate this message, so a tombstone would be wrong.

Evidence: squatch/effects.py:58 appends effect_intent before the action; squatch/effects.py:63 appends effect_completion after it; squatch/journal.py:134 json.dumps(asdict(event), allow_nan=False) runs before the write, so an unencodable body raises with no torn segment line. Reopen if an actual non-JSON action result is found in production code, or if reconcile's stranded-key report turns out not to name the key clearly enough to find the programming error.
