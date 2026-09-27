---
verdict: snag
reviewed_sha: bda60c625858b6e47f27c6fb87afc1ed3df335a8
produced_by_spec_version: '1.0'
produced_at_sha: bda60c625858b6e47f27c6fb87afc1ed3df335a8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The wiring, fencing and tests cover the listed cases. One gap remains: a run's lift can be cited as evidence for an artifact that an earlier run already delivered and committed. A later no-op run of the same ticket would then pass the empty-diff check.

## Findings
- correctness_review at squatch/stages.py:91: `completed_output_lift` accepts any registered artifact path named in this run's `lift/<stem>/<run_seq>/...` result. `lift_ticket_files` builds `paths` from `rglob` over the worktree outbox, so the list includes every file there, tracked ones too. It also returns those paths even when nothing changed (`commit: None`). Suppose an earlier run lifted `tickets/<stem>/<registered report>` and that file is now committed on main. A rerun branches from that base, so its worktree already holds the old report. If the implementer then does nothing, this run's lift still names the report and the worktree status is clean. `output_lift_allows_empty` therefore returns True and the empty diff is admitted on evidence from the earlier run. The ticket's Definition of rejected lists exactly this ('cross-run evidence'). The `stale` test only covers a journal key carrying a different run_seq, not a stale file carried inside the current run's lift. I have not reproduced this with a test; it follows from `lift_ticket_files` in `squatch/stages.py` around lines 1013-1057. (paved road: Only count an artifact that this run actually produced. In `output_lift_allows_empty`, require at least one worktree `git.status` entry (untracked or modified) that names a registered, non-`run.md` artifact under `tickets/<stem>/`. Also require that same path to be named in the completed lift result. Add a test in `tests/test_stages.py` that commits a valid registered report under `tickets/<STEM>/` on main, runs an implementer that writes nothing, and asserts the 'no committed diff' verification finding.)
