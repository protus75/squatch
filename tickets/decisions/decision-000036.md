---
id: decision-000036
kind: decision
link: box-000036-e8451b9b
reopen_after_days: 180
message: box-000036-e8451b9b
---
No action. The message proposes no work and calls the current setup acceptable. It is also partly out of date: the child processes do not depend on where pytest is launched from. tests/test_lockfile.py starts three `sys.executable` children, not two (lines 120, 141 and 178). Each one pins `cwd=Path(__file__).parents[1]`, which is the checkout root derived from the test file's own path. Because they run with `python -c`, the interpreter puts that cwd first on `sys.path`, so `import squatch` resolves to the checkout's package whatever directory pytest was started from. The only case this misses is running the suite without a checkout, and nothing does that: the engine runs from its own checkout (ENGINE_ROOT, see decision-000032), and no rendered ticket or plan item packages the tests into a wheel. Adding a PYTHONPATH injection or a note for that case would be speculative work with no incident behind it, which the anti-bloat law rules out. No rendered ticket or decision covers how the lockfile tests spawn children, so a tombstone would be wrong. Reopen if a ticket introduces a test run from an installed wheel or from outside the checkout. That ticket should make the child import path explicit in the same change.

Evidence: tests/test_lockfile.py:120, 141-146 and 178-184 each spawn `[sys.executable, "-c", ...]` with `cwd=Path(__file__).parents[1]`. Under `-c`, the child's cwd goes first on sys.path, so it imports squatch from the checkout. Engine execution from its own checkout: decision-000032 (`go()` resolves ENGINE_ROOT). No open or merged ticket runs the suite from an installed wheel.
