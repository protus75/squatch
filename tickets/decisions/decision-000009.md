---
id: decision-000009
kind: decision
link: box-000009-1fb6ab6c
reopen_after_days: 90
message: box-000009-1fb6ab6c
---
No action needed. The test does pin the behavior the plan guarantees. `Journal.append` is the only append path in squatch/journal.py, and its docstring says it fsyncs each event before returning. Section 6 requires write-ahead fsync before return for intent, completion, Timer, Signal and cap events. Asserting one fsync per append, plus an inode check that the fsync hit the active segment, is a direct test of that. The section 6 rule that background appends fsync at least every 3 seconds is a floor for a path that does not exist yet. Nothing has a batched or background append API. Such a path would have to be a separate entry point, because the load-bearing events must still fsync on every append, so it would not change what `append` guarantees or break this test. Loosening the test now would weaken the pin to prepare for a design that doesn't exist, which is the speculative work the anti-bloat law rules out. No rendered work covers this, so there is nothing valid to tombstone against. Reopen when a ticket adds a batched or background append path to the journal. That ticket should add its own test for the 3-second limit and leave this pin in place.

Evidence: tests/test_journal.py:151-160 (`test_append_fsyncs_before_returning` asserts one fsync per `append` on the active segment's inode). squatch/journal.py:124-139 (`append` is the only append method; its docstring reads 'Append one event and fsync it before returning (write-ahead)', and it calls `os.fsync(self._fh.fileno())` every time). There is no background or batched append API in squatch/journal.py. SQUATCH_PLAN.md:977 (section 6: intent and completion events are fsync'd before anything acts on them; background appends fsync at least every 3 seconds, an engine constant).
