---
id: decision-000029
kind: decision
link: box-000029-6accc5a9
reopen_after_days: 180
message: box-000029-6accc5a9
---
No action. The message proposes no work and calls both tests acceptable. It only notes which test carries which proof, and the code already makes that split. `test_module_never_imports_shell_machinery` (tests/test_git.py:295-300) says in its own comment that it is the D1 tripwire: it scans the module text for `subprocess`, `shell=True`, `os.system`, `shlex` and `rm -rf`. `test_env_is_required_keyword` (tests/test_git.py:51-56) pins that `env` must be passed by keyword. That is the constructor contract every production `Git(...)` call already follows with `env=child_env(...)` (decision-000022). The behavioral proof is a separate block, marked `# --- one real repo through the real seam ---` (line 303 on). Those tests build `Git(SubprocessExec(), env=..., timeout=60.0)` (lines 321, 376, 395, 428, 459) and run real git argv against a temp repo. The module docstring (lines 6-7) says the same thing. Both pins are cheap, so updating them on a refactor is fine. They guard the argv-wrapper rule, and a rename-in-place refactor updates tests in the same change anyway. Adding a comment or rewriting the pins would be churn with no incident behind it, which the anti-bloat law rules out. No rendered ticket or decision covers test_git.py pin shape, so a tombstone would be wrong.

Evidence: tests/test_git.py:6-7 (docstring names the real-seam proof); :51-56 (`test_env_is_required_keyword`); :295-300 (`test_module_never_imports_shell_machinery`, whose comment labels it D1); :303 onward (real-repo tests through `SubprocessExec` at :321, :376, :395, :428, :459). Reopen if a refactor of squatch/git.py has to weaken or delete either pin instead of updating it, or if the real-seam block stops constructing `Git` over `SubprocessExec`.
