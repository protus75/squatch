---
id: decision-000010
kind: decision
link: box-000010-0cd0f019
reopen_after_days: 30
message: box-000010-0cd0f019
---
No action needed. The suggestion is stale. It describes an early state of squatch/seams.py in which deliverable 5 still had to add the section 15 process-seam pieces and the notifications seam was deferred. Every piece it lists is now in the file. There is nothing left to extend and no new work to author. None of the rendered stems is clearly the deliverable-5 ticket that added the process-seam pieces, so tombstoning against one would mean guessing the link. `notify-transport` probably owns the `Notifications` seam, but it covers only part of this message. That is why this is a decision and not a tombstone. Reopen if a section 15 seam requirement is found to be missing from squatch/seams.py, or if production code calls a process, notification, or filesystem primitive directly instead of going through the seam.

Evidence: squatch/seams.py: `ProcessExec` Protocol (line 23); `Filesystem.write/replace` (lines 39, 43); `Notifications.notify(argv)` Protocol plus an implementation (lines 68, 83); `ExecutableNotFound`, the error raised when `argv[0]` cannot be resolved, which is re-raised from `FileNotFoundError` (lines 96-98, 131-132); module-level `kill_group(pgid)`, which sends SIGKILL to the process group (line 101); `SubprocessExec.run`, which starts the child with `start_new_session=True` (line 130) and has the spawn-time `on_spawn(pid)` hook, where the pid is also the pgid (line 137); the single `_kill_and_wait` path that runs on both timeout and outer cancellation (lines 151-157, 181-183). `notify-transport` is in merged_work. I could not run git history, so I have not confirmed which ticket added these pieces.
