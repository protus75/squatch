---
id: decision-000018
kind: decision
link: box-000018-9aa4e3b0
reopen_after_days: 90
message: box-000018-9aa4e3b0
---
No action needed. The message is stale. It is a bootstrap-ingest note from deliverable 5 saying the section 15 kill-path parts of `SubprocessExec` were deferred until their first consumers existed. Those consumers have since merged, and the deferred parts are now built. `SubprocessExec.run` (squatch/seams.py:120) takes an `on_spawn` hook and calls it with the child's pid right after spawn (seams.py:136-137). Because of `start_new_session`, that pid is also the process-group id. The run-to-group binding exists in providers.py. The CLI call passes `on_spawn=self._bind` (providers.py:443), `_bind` stores the pgid (482-483), and a `finally` clears it when the call returns (455-458). `abort_current` (485-488) sends `kill_group` to the bound group, which is the consumer this message was waiting for. At spawn, `FileNotFoundError` from `create_subprocess_exec` becomes `ExecutableNotFound` (seams.py:131-132). If spawn is cancelled, the stdin handle is closed in the `finally` (133-135) and `CancelledError` propagates unchanged, which is the right outcome for a cancellation. The message asks for nothing more. `kill-executor-abort` is probably the merged ticket that added this, but its Goal line doesn't name the seam, and tombstoning against it would mean guessing the link. So this is a decision, matching decision-000010 for the sibling deliverable-5 note.

Evidence: squatch/seams.py:118-137 (on_spawn parameter, pid-as-pgid hook, FileNotFoundError -> ExecutableNotFound, stdin closed in finally); squatch/providers.py:401, 441-458 (on_spawn=self._bind, _pgid cleared in finally), 482-488 (_bind, abort_current -> kill_group). Reopen if the `kill <run>` path or `abort_current` is found not to reach an in-flight child's process group, or if a spawn-time cancellation leaks a child or a file handle.
