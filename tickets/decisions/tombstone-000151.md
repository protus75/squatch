---
id: tombstone-000151
kind: tombstone
link: verification-attribution
reopen_after_days: 90
message: box-000151-3bc410a2
---
The gap this message describes is already closed by merged work. It asked for a stopgap in the Verification paved road: when a command is red on the base too, the road should say to file it, but only until base-diff attribution lands. verification-attribution (merged) is that attribution. I checked squatch/stages.py:371-418. When a `## Verification` command is red on the branch, `Verification.check` re-runs it in a detached worktree at `slip.base`. If the command is also red there (`base_rc != 0`), the gate adds no finding. It records the command with `attribution="base"`, and `_file_base_red` (:438-444) files a `failure_report` into the Box with `outcome="base_red"`. So a pre-existing red never produces a finding that carries the 'exit 0 on the committed branch' road (:340). That road now appears only in two cases. One is a command that is green at the base and red on the branch, which the branch really did break. The other is a failed attribution attempt (:389-410), where the road is still correct because the branch's red has not been excused. The interim wording the message wanted has nothing left to cover. Reopen if a regeneration removes or bypasses the base re-run, if a base-red command ever produces a `verification` finding, or if attribution failures become common enough that the road needs to name the base-red case.
