---
id: decision-000020
kind: decision
link: box-000020-86330f18
reopen_after_days: 90
message: box-000020-86330f18
---
No action for now. The facts in the message are correct, but no production path depends on them. `Git.init` (squatch/git.py:56-59) does run `git init -q -b main`, and `-b` needs git 2.28 or later. Nothing in engine code checks a git version floor. `doctor` runs `git --version` (squatch/doctor.py:138), but it only reports what git answers and never compares it to a minimum. However, no module under squatch/ calls `Git.init`. The engine works on existing host and self checkouts through `worktree add`, so the startup refusal would be guarding a verb the drain never uses. If an older git did reach `init`, it would fail on the unknown switch. The argv wrapper would raise and the call would fail closed, so a pre-check would only change the error message. A new startup gate with no incident behind it is the speculative gate accretion that the anti-bloat law rules out. The open ticket `startup-interpreter-floor` covers only the interpreter (D1), not git, so tombstoning against it would be wrong.

Evidence: squatch/git.py:59 `await self._run(repo, "init", "-q", "-b", "main")`. A grep for `.init(` under squatch/ finds no caller. squatch/doctor.py:127-139 probes `--version` without a floor comparison. SQUATCH_PLAN.md line 1585 lists Git version only as something doctor reads, not as a floor. Reopen if a production path starts calling `Git.init`, if the engine starts using another git feature that needs a specific version on the drain path, or if an incident shows an old host git failing silently or ambiguously instead of loudly.
