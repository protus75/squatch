---
verdict: snag
reviewed_sha: d9a3633bcd31246ea82626c248171094db2447c4
produced_by_spec_version: '1.0'
produced_at_sha: d9a3633bcd31246ea82626c248171094db2447c4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The queue's structure matches the ticket and the checks are green. However, the mechanical rung matches paths with different rules than the config contract and the rest of the engine use, so some declared strategy paths will never resolve.

## Findings
- correctness_review at squatch/mergequeue.py:252: `_path_matches` does not follow the `merge.strategies[].paths` contract. The plan declares these entries as `<path-prefix>`, and the engine's existing prefix test (`stages._outside_fence`) treats `p` as matching `path == p or path.startswith(p + '/')`. This diff does two different things. First, a prefix without a trailing slash matches only by exact name or fnmatch, so a declared `generated` or `docs` never matches `generated/x.lock`, and that conflict drops to rung 2 even though the host declared a strategy for it. Second, it runs `fnmatch.fnmatchcase` on every declared entry, which gives unspecified glob powers to `*`, `?` and `[...]`. A `*` matches across `/`, so a single entry can silently cover far more paths than the host meant. The result is either an unused strategy or a union/regenerate strategy applied to paths nobody declared. This is a fail-open widening of an allowlist, and it lands on paths in the engine-plane safety inventory. (paved road: Match exactly the way the scope-fence gate does: `path == declared or path.startswith(declared if declared.endswith('/') else declared + '/')`. Drop `fnmatch`. Add a test with a declared prefix that has no trailing slash and a nested conflicted file, and a test showing a glob-looking entry is not expanded.)
- correctness_review at squatch/mergequeue.py:223: The rung-2 return paths inside `_rebase` call `rebase_abort` themselves, and they sit inside a `try` whose `except BaseException` also calls `rebase_abort` and then re-raises. If that first in-loop abort raises `GitError`, the handler aborts a second time, swallows the second failure, and re-raises the original `GitError` out of `admit`. The admission then ends with an untyped exception: no conflict-facts journal record, no `Admission`, and no rung-2 handoff. That contradicts the typed unwind-then-handoff contract. It is also inconsistent with the pre-start and after-start rebase failures, which come back as a typed `CandidateRebaseFinding`. I'm not certain this can happen in practice, since it needs `git rebase --abort` itself to fail. (paved road: Do the abort once, in one place. For example, have the loop return the rework facts, then abort in a single `finally`/unwind step. If that abort fails, map it to a typed `CandidateRebaseFinding` admission (with the facts journaled) instead of letting a raw `GitError` escape.)
