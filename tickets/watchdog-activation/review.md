---
verdict: snag
reviewed_sha: 51063787ca9dc5dbd0d45674cd7918d3409851da
produced_by_spec_version: '1.0'
produced_at_sha: 51063787ca9dc5dbd0d45674cd7918d3409851da
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The wrapper is bound correctly: drain and serve bind at construction, the LLM seams are unchanged, the signal bodies and identities match the spec, and all checks are green. One production defect remains: the mutation sampler synchronously re-reads and re-hashes every file under each scope-fence directory on every provider stdout event and every second, and this is unbounded for continuation tickets whose fence is `tickets`.

## Findings
- correctness_review at squatch/watchdog.py:172: `WatchdogLLM._sample` walks `fs.list(root, "**/*")` for every fence prefix and reads and sha256-hashes each file. It is called from `on_event`, which runs synchronously inside `CliClient`'s `on_stdout_line` for every streamed line, and from the 1 s `_observe` loop. Scope fences may name directories: every `phase3-continue-*` ticket fences `tickets`, which is currently 1004 files and 9.3 MB, and `phase4-continue` does the same. So each agent stdout line blocks the event loop while roughly 9 MB is re-read, and an implement call streams hundreds to thousands of lines. That stalls the drain and serve loop, including the LLMEffect deadline sleeper and serve's poll/kill tasks, and turns a monitoring hook into the dominant cost of a run. The tests only use a single-file fence (`output.txt`), so they never exercise this. I am confident this is a real production hazard. Whether it blocks merge is a judgement call, since it degrades throughput rather than producing wrong verdicts. (paved road: Bound the sampling cost: don't sample from the per-line `on_event` callback. Sample only at call boundaries and on the observer tick. Keep the tick on the injected `Sleep` seam at a coarser interval, and compare cheap metadata (size/mtime via the filesystem seam, or the worktree's git status/HEAD through `git.py`) instead of re-hashing file contents. Add an activation test with a directory fence holding many files that asserts the number of per-event reads stays bounded.)
