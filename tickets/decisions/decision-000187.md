---
id: decision-000187
kind: decision
link: box-000187-32360b16
reopen_after_days: 90
message: box-000187-32360b16
---
No ticket. The gap the message describes is closed. It comes from the bootstrap ingest window, before the self-upgrade handoff (prompt 13's deliverable) existed. At that time the drain's `Upgrade` seam received only (admitted stem, parked set), so it could not see which files an admission changed. Today the drain works out the changed-file set itself. `Drain._upgrading` (squatch/drain.py:435-441) takes the admitted squash commit and runs `git.diff_names(repo, commit^, commit)`. It keeps only paths under `UPGRADE_PREFIXES`, and it returns an empty list for a host-only diff or for an `already_satisfied` settle that has no commit. This is the message's second option: a git read of the admitted commit, keyed on the commit sha that the merge admission already records. `_handoff` (drain.py:443-457) then journals a handoff signal that carries the admitted stem, `facts.commits[stem]`, the touched paths and the parked set. It also reports the touched paths to the operator. So the `Dispatched` record never had to carry the changed files, and nothing remains to build. No rendered open ticket, merged Goal line or decision names the self-upgrade trigger, so a tombstone link would be invented. That makes this a decision.

Evidence: squatch/drain.py:433-468: `_upgrading` derives the touched engine-plane paths from `git diff_names` over `commit^..commit`, filtered by UPGRADE_PREFIXES. `_handoff` journals HANDOFF_SIGNAL with admitted, commit, touched, parked and argv. `_exec` re-execs through `uv`. SQUATCH_PLAN.md:594 names the re-exec as prompt 13's deliverable. The message's own evidence field is None. Reopen if a regeneration removes `_upgrading`'s diff read, if the handoff stops recording the touched paths, or if a journal shows an admission touching squatch/** or specs/** with no handoff signal.
