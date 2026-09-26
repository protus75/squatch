## Outcome
premise_failed

## Surprises / judgment calls
The current branch is control-inbox and began clean. Neither squatch/control.py nor tests/test_control.py exists; prior attempt code is absent. Read the ticket, both Context files, plan section 20, daemon task tests, and the filesystem and journal implementations. The plan registry and ticket fence omit the filesystem seam needed for durable publication.

## Dead ends
Stopped before implementation on a scope authoring defect: squatch/seams.py is outside the fence. Filesystem exposes only write, replace, and unlink. LocalFilesystem.write fsyncs the temporary file but calls os.replace without fsyncing the containing directory (or newly created parent entries), so successful publication is not guaranteed durable across a system crash. Both write and replace overwrite destinations; neither provides atomic no-overwrite publication. Checking existence before write would race concurrent publishers. The required durable inbox cannot obtain those guarantees through the existing seam; implementing raw filesystem operations or a parallel filesystem adapter in control.py would bypass the mandated seam. The paved road is to authorize the seam extension and its tests in a revised plan registry and ticket fence. No implementation or verification commands were run after identifying this blocker; no code was changed or committed.

## Second problems filed
None. The filesystem limitation is a direct blocker for this ticket, not an adjacent repair.

## Resolved engine/model
OpenAI / GPT-6 (Codex; exact serving variant unavailable).

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 3 minutes of feasibility inspection before the fence blocker.
