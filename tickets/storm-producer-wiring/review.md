---
verdict: snag
reviewed_sha: a5a32c23cedab3ebfbcb86d0786b7b8feb29023a
produced_by_spec_version: '1.0'
produced_at_sha: a5a32c23cedab3ebfbcb86d0786b7b8feb29023a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The box.py and daemon.py wiring looks correct: the box write happens before the recorder call, the identity is <box_id>/<reports>, the token is reset in finally, the binding is scoped to a state directory, and the ledger's key-based dedup covers replay. The tests fall short of several acceptance criteria, and the dormancy test is weaker than the ticket requires.

## Findings
- correctness_review at tests/test_storm_producer.py:65: Acceptance criterion 3 requires tests that reconciliation writes each missing occurrence with the Journal clock's append-time timestamp and that already-recorded occurrences keep theirs. No test reads event.ts or compares it with the injected clock. (paved road: Enqueue unbound, then enter the producer scope with a known clock and assert each reconciled event.ts equals the clock value at append. Then re-enter the scope and assert the earlier events' ts are unchanged and no new events were written.)
- correctness_review at tests/test_storm_producer.py:65: Acceptance criterion 3 and the Scope-in crash case need reconciliation across rolled journal segments and several missing arrivals on one record, recorded as <id>/1..<id>/n in box seq then n order. The only reconciliation test has one missing report per record, and no test rolls a journal segment. (paved road: Add a test that builds a record with reports >= 3 while unbound, rolls the journal segment by the Journal's own mechanism with some occurrences already recorded in the old segment, enters the scope twice, and asserts the exact ordered ids with no duplicates.)
- correctness_review at tests/test_storm_producer.py:1: Acceptance criterion 4 and the Scope-in require test_storm_producer.py to prove the producer emits no trip signal, P0 report, notification, or dispatch hold. No test asserts this. The window assertion at line 90 (`assert ledger.window(...)`) only checks that the result is truthy. (paved road: After the scoped arrivals push a signature over THRESHOLD, assert the journal holds only storm_occurrence signal events (no trip or other signal kinds), that the Box got no new P0 or failure report, that no notification seam was called, and that the scheduler or dispatch state shows no hold. Replace the truthy window assert with an exact OccurrenceWindow comparison.)
- correctness_review at tests/test_storm.py:86: The ticket asks for AST call-site reachability rooted at squatch/__main__.py and squatch/drain.py. The new test only scans those two files and only for bare-name calls (ast.Name). It misses attribute calls such as `daemon.compose_daemon_storm_producer(...)` and `box.scoped_occurrence_recorder(...)`, and any call from a module that __main__ or drain reaches transitively. A production activation could get past it. (paved road: Walk the import closure from squatch.__main__ and squatch.drain, as the old test did. In every reachable module, fail on any Call whose func is an ast.Name or an ast.Attribute whose attr is compose_daemon_storm_producer or scoped_occurrence_recorder. Skip only the definition sites in daemon.py and box.py, and only the definitions themselves.)
