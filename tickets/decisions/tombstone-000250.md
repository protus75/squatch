---
id: tombstone-000250
kind: tombstone
link: decision-000242
reopen_after_days: 90
message: box-000250-946c21f0
---
The headroom risk this message describes can no longer happen. Both seeds it names, requisition-review-author and phase2-exit, are in merged_work. Every later phase through phase6-exit has also closed, so neither seed will be dispatched again at a resolved `high` effort, and the 240k bound cannot refuse either one. decision-000242 already covers how the render bound interacts with effort for these bootstrap-floor Phase 2 seeds. Section 19's ladder-top render check exempts them, and all of them have merged. Every ticket authored or seeded after them is measured by requisition review at the tightest `max` bound with 0.75 headroom before it commits, so no non-exempt ticket can reach dispatch with a render that a higher-effort bound would refuse. The message warns that the exit seed's Context files keep growing through Phase 2, but phase2-exit has merged and Phase 2 is closed. Trimming Context in those seeds now would mean regenerating finished work with no failure behind it. The message gives no evidence and comes from bootstrap-ingest, so under D10 that work would be speculative. Reopen if requisition-review-author or phase2-exit is regenerated or re-dispatched, or if any ticket that passed requisition review is later refused RenderRefused(over_bound) at its resolved effort.
