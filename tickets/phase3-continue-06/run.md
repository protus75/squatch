## Outcome
ok

## Surprises / judgment calls
Section 20 supports the required fences; the reviewed defects were seed authoring defects, not plan defects. Authored exactly merge-queue-activation, rework-activation and phase3-continue-07. Reused the previous attempt's proof structure after checking all 11 pinned Context blobs against base 6c75000a0767ef70e27884db0df5a3824a22cae8: each exists, its size matches, and none contains the data-block delimiter.

Merge activation now specifies a merge.py-local subtype overriding public admit to capture candidate HEAD before super().admit, with finally cleanup of the head and Invoice by (stem, run_seq). It does not require a private queue override or extra Context. Seven signatures were copied verbatim and checked against the base so truncated requisition excerpts retain interface evidence. Approval uses review.md through Merge._approval/load_review, pinned to the captured pre-rebase head. The migration/preservation criteria name tests/test_mergequeue.py; the production factory proof names tests/test_daemon_composition.py. Merge.admit and Pipeline.run preservation is a Scope out constraint.

Rework composition takes every constructor dependency explicitly and consumes the same production queue after slot unwind. The successor gives background-consumers ownership of tests/test_daemon_tasks.py and control-inbox ownership of squatch/control.py and tests/test_control.py; control-inbox also hooks the task tests. Exact Context maps, ownership, new-path sets, predecessor closure and both shrinking suffixes are pinned.

Synthetic max-effort renders: merge-queue-activation 106499, rework-activation 78913, phase3-continue-07 88684 characters, all below 120000. Only tests/test_seeded_phase3_06.py is committed; the three seed files and this record remain uncommitted for the engine.

## Dead ends
Initial seed lint rejected generic verification criteria without an explicit command or artifact. Named the exact full-suite command and the daemon artifact, then reran the required checks successfully. Replaced the previous private _rebase override contract with the public admit seam rather than widening the pinned five-path Context.

## Second problems filed
None.

## Resolved engine/model
OpenAI Codex; GPT-6 (specific serving variant not exposed).

## Predicted vs actual
Expected 75 minutes; actual approximately 15 minutes. uv run pytest tests/test_seeded_phase3_06.py -q: 8 passed. uv run pytest -q: 926 passed in 40.23 seconds. Both commands exited 0.
