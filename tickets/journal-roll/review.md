---
verdict: snag
reviewed_sha: 517728792a221f9c0716461028dd03cc4b8cf7b4
produced_by_spec_version: '1.0'
produced_at_sha: 517728792a221f9c0716461028dd03cc4b8cf7b4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The roll trigger, ordered naming, immutability and cross-segment replay match section 20, and all tests pass. One fail-open path remains: the helper that finds the active segment's age anchor on open silently discards corruption.

## Findings
- correctness_review at squatch/journal.py:234: `_first_event_time` catches `ValueError`/`JSONDecodeError` from the first line of the active segment and returns `None`. It also skips empty lines with `continue`, but `_read_segment` treats an empty line as corruption. When the first record is corrupt or blank, the writer opens with `_active_started = None`. The next `append` then sets the anchor to its own `now`, so a segment whose first event is older than 24h keeps growing past the fixed age bound. Nothing reports the corruption. This breaks the 24h roll guarantee and the fail-closed rule: the reader raises `JournalCorruption` on the same bytes, but the writer quietly works around them. I'm fairly but not fully sure this path matters in practice, because `read()` would still raise later. The age-bound violation happens regardless. (paved road: Fail closed. Parse the first line the same way `_read_segment` does, and raise `JournalCorruption(f"{path}:{n}: {e}")` on `ValueError` rather than returning `None`. Treat an empty line as corruption, not something to skip. Return `None` only when the segment has no lines at all. Add a case in `tests/test_journal_roll.py` showing that opening a journal whose active segment has a corrupt first line raises `JournalCorruption`.)
