---
verdict: snag
reviewed_sha: bb23506fbed3370a978032202c92dec4c41f7db1
produced_by_spec_version: '1.0'
produced_at_sha: bb23506fbed3370a978032202c92dec4c41f7db1
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The inbox, durable publish seam and daemon hook meet the ticket, and the check report is green. One crash-replay path is not idempotent: a request whose filename does not match its request_id gets a new journal decision on every replay after a crash before removal.

## Findings
- correctness_review at squatch/control.py:111: The filename/request_id mismatch branch always calls self._append(path.stem, decision) and then self._fs.remove(path). It never checks the decision already journaled for that file. If the process crashes between the append and the remove, every later pass appends another identical 'invalid' decision for the same file until a removal succeeds. The unparsable-payload branch just above guards this same crash point with `if decisions.get(path.stem) != decision`, and test_terminal_invalid_decision_is_not_duplicated_after_remove_crash covers only that branch. The result is that one file can produce duplicate terminal decisions in the journal, which is permanent and versioned. That contradicts the ticket's exactly-once consumption requirement for the one input class that has no replay test. (paved road: Apply the same guard to the mismatch branch: build the decision, append it only if `decisions.get(path.stem) != decision`, then remove the file. Add a parametrized case to tests/test_control.py that publishes a valid request under a different filename, crashes in remove, replays, and asserts exactly one 'invalid' signal for that key.)
