---
id: tombstone-000164
kind: tombstone
link: spine-harvest
reopen_after_days: 30
message: box-000164-d277ef51
---
Merged work already delivers this. The message comes from bootstrap ingest and describes the Phase 1 runner, where the `Pipeline` seam returned a bare outcome string and the `stopped:` line pointed only at the engine log. It also says the Phase 2 harvest would widen the seam. spine-harvest (merged) is that harvest, and spine-diagnosis (merged) builds on it. The current code shows both changes in place. `Pipeline.run` (squatch/runner.py:82) returns a `Delivery`, and that object carries `findings` (:410). The non-ok terminal stores `finding_codes` and the `reason` built from them, plus the `diagnosis` record (:455-459). The `stopped:` line (:480-481) now points the operator to `detail: tickets/<stem>/attempts/<run_seq>/` (:401), the harvested attempt directory in the ticket plane, and not to the engine log. Spine-harvest's allowlist extraction puts the check invoice, the review snags and the merge findings there, and the diagnosis lessons go to `tickets/<stem>/diagnosis.json`. The deferral the message describes has already been delivered. Reopen if a regeneration narrows the `Pipeline` seam back to a bare outcome, if the `stopped:` line stops naming the attempt directory, or if a harvested attempt directory is found to be missing the findings behind its terminal.
