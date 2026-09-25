---
verdict: snag
reviewed_sha: 2a0c03f1f43e66f2911dcfbb24289e60b066967e
produced_by_spec_version: '1.0'
produced_at_sha: 2a0c03f1f43e66f2911dcfbb24289e60b066967e
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Both members and both unit pins satisfy their stated observables, the check report is green, and every changed path is inside the fence. But the members get their routing fixture by overwriting the private `_config` attribute on the bench's Runner and Drain, which is the case the ticket's Definition of rejected says to stop on with premise_failed.

## Findings
- correctness_review at eval/shakeout/ladder_group.py:113: `_configure` swaps configs by assigning `bench.config`, `bench.runner._config`, and `bench._drain._config`. `eval/shakeout/bench.py` offers no public way to run under a routing fixture: `Bench.configure` only takes `fake` and `sleep`, the config is loaded once in `__init__` and handed to Runner and Drain, and no other shakeout group touches these private attributes. The ticket's Definition of rejected says: "Stop and answer `premise_failed` naming the member ... if the bench as landed cannot run under a routing fixture other than the instance's." The diff works around that premise with private-attribute patching instead of stopping. That couples both members to Runner and Drain internals, and it can silently desync from state bench.__init__ built from the original config: `bench.state_dir`, the Redactor, and the journal path all assume the original `state_dir` survives the swap. I am not certain whether the ticket author would count this patching as 'the bench can run under a routing fixture'. I am reporting it because the ticket names this exact condition as a stop, and the change needed (a bench seam) is outside the fence. (paved road: Answer `premise_failed` naming `identical_terminals_climb` and `identical_terminals_reject_when_exhausted`: the landed bench has no public routing-fixture seam. That gets a bench change filed (e.g. `Bench.configure(config=...)`, or accepting a Config at construction, rebuilding Runner and Drain from it), and this ticket reruns on top of it. Do not overwrite `_config` on engine objects from a member module.)
