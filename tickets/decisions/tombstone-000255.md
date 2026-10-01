---
id: tombstone-000255
kind: tombstone
link: phase2-exit
reopen_after_days: 90
message: box-000255-6b759807
---
phase2-exit is in merged_work, so its verification step already ran and the Phase 2 exit has been read closed. Every shakeout group the message names is also in merged_work: tickets, stages, driver, reconcile, merge, providers, drain and ladder. Phase 3 through Phase 6 have each closed since then, up to phase6-exit. The message is correct that a `git diff --name-only` command exits 0 whatever it lists, so on its own it shows the criterion was checked by the agent, not enforced by a gate. The message also says the real enforcement is already in place: the scope-fence gate and the code lane's `tickets/**` refusal. Those gates guarded every merged diff, so no out-of-fence path could reach main through these tickets. Citing those gates in the seeds now, or dropping the listing lines, would mean regenerating finished deliverables with no failure behind the change. Section 17 also counts that kind of edit as change history in spec or ticket prose. The message gives no evidence and comes from bootstrap-ingest, so under D10 the work would be speculative. Reopen if phase2-exit or any shakeout group is regenerated or re-dispatched, since the verification line can then cite the fence gate at no extra cost. Also reopen if a later authored ticket's `## Verification` relies on a command that is always exit-0 as its only check of a criterion that no gate enforces, or if a merged diff is found to touch a path its fence should have refused.
