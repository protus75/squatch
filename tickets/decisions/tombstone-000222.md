---
id: tombstone-000222
kind: tombstone
link: outbox-only-admission
reopen_after_days: 90
message: box-000222-7408445f
---
Merged outbox-only-admission settles a run-only ticket whose deliverable is lifted from its OUTBOX with no code diff. Verification takes an allow_empty flag (squatch/stages.py:345, :362), which is set when the run lifted known output paths or seeds (stages.py:932, merge.py:380, merge.py:599). So the empty-diff refusal the message describes no longer applies to an outbox-only run. The Phase 3-4 run tickets use this route: tickets/soak-run/ticket.md depends on outbox-only-admission and leaves its daemon-soak-report.json in its OUTBOX, and soak-run and reliability-run both merged 'through the ordinary lane'. The Phase 2 diagnosis-eval seed's code-lane report is a historical alternative shape. It does not block any ticket from settling. Reopen if a run-only ticket ends in gate_failed on the empty-diff verification finding despite a schema-valid OUTBOX artifact, or if a regeneration of outbox-only-admission drops the allow_empty path.
