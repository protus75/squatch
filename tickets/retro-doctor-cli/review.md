---
verdict: snag
reviewed_sha: 15db44a01e1a9d490acecfc66a3a444b9af693be
produced_by_spec_version: '1.0'
produced_at_sha: 15db44a01e1a9d490acecfc66a3a444b9af693be
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The retro verb matches its contract: it reuses the single governed Retro composition for both the manual and drain paths, and its output and exit behavior follow the ticket. The doctor verb's git check is the problem: it runs git directly through the process seam with the full, unfiltered operator environment, so any provider API key in that environment is handed to a child process that does not need it, and the call skips the git.py wrapper.

## Findings
- correctness_review at squatch/doctor.py:126: `Doctor._git` runs `self._process.run(["git", "--version"], cwd=self._repo, env=self._env, ...)`, where `self._env` is the raw operator env passed in from `_doctor` in squatch/__main__.py. Every other git call goes through `Git(process, env=child_env(env, {p.auth for p in config.providers if p.auth}))`, which removes provider keys first. Doctor does not, so provider API keys reach a git subprocess, breaking the engine's inherit-minus-secrets rule. It also bypasses git.py, the one wrapper where git exec and child env are enforced. (paved road: Build the git child env with `child_env` using the provider auth names from the loaded config. If config fails to load, fall back to an env with no provider keys. Better still, add a small `Git.version()` to git.py and call it through a `Git` built with that stripped env, so doctor's git probe still runs through the process seam but also through the wrapper. Add a test that the env the injected process receives contains no configured provider auth variable.)
