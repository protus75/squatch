---
id: decision-000006
kind: decision
link: box-000006-f7f3eb03
reopen_after_days: 30
message: box-000006-f7f3eb03
---
No action needed. The message says a read-only journal reader doesn't exist, but it already does. squatch/journal.py defines module-level `read_segments(state_dir)` (line 173) and `read_events(state_dir)` (line 181). The `read_events` docstring says it never creates the journal dir, never truncates a torn tail, and never holds an append handle, and that a missing journal reads as empty. Read-only callers already use it: in squatch/__main__.py, status and projection reads at lines 177, 319, 518 and 602 call `read_events`. `Journal(...)`, which truncates and opens for append, is built only where the caller writes to the journal (__main__.py:489 and 609, runner.py:180). I couldn't check git history to prove which rendered ticket added the reader. `status-projection` is the likely one, but that's unconfirmed, so I'm recording a decision instead of tombstoning against it. Reopen if a read-only caller is found that builds `Journal(...)`.

Evidence: squatch/journal.py:173-189 defines read_segments/read_events as non-writer readers. The grep for `Journal(` in squatch/ found only writer sites: __main__.py:489, __main__.py:609 and runner.py:180. Read-only sites use read_events: __main__.py:177, 319, 518 and 602. Constructor truncation (journal.py:92 `_truncate_torn_tail`) is reached only through `Journal.__init__`.
