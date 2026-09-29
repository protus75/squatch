---
verdict: snag
reviewed_sha: 8a2768996c998469ccc9a02df68e7b6404776f53
produced_by_spec_version: '1.0'
produced_at_sha: 8a2768996c998469ccc9a02df68e7b6404776f53
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The projection folds, additive fields, and scorecard wiring are correct and stay inside the fence. However, `_status` now fails with an unhandled `GitError` wherever HEAD cannot be resolved, and `tests/test_status.py` does not prove what its acceptance criterion requires.

## Findings
- correctness_review at squatch/__main__.py:131: `asyncio.run(git.rev_parse(cwd, "HEAD"))` runs inside a try block that catches only `JournalCorruption` and `BoxCorruption`. A `GitError` escapes `_status` as an unhandled exception, with no `Refusal`, no paved road, and no defined exit code. `Git.rev_parse` runs `rev-parse --verify HEAD`, so this happens in a repo with no commits yet or in a cwd that is not a git checkout. Before this change, `status` needed no git at all. This breaks the ticket's requirement to preserve the CLI exit/output contract and the fail-closed rule that every failure ships a paved road. No test covers it. (paved road: Catch `GitError` in `_status` and raise `Refusal(f"cannot resolve HEAD: {e}", "<paved road, e.g. commit an initial revision or run status inside the host checkout>")`, the same way `_run` handles `GitError`. Add a `tests/test_status.py` or `tests/test_cli.py` case where the stub `rev_parse` raises `GitError`, and assert the refusal exit code and message.)
- correctness_review at tests/test_status.py:1: Acceptance criterion 1 is only partly met. The criterion requires `tests/test_status.py` to prove every preserved field and rendering, exactly the three additive fields, and all deterministic folds. The new tests assert only `merged`, `in_flight`, `spend_usd`/`calls`, `box_activity`, `tombstone_digest`, and two section headers. Nothing asserts the `blocked` fold `(stem, unmet_dependencies)` for a confirmed unmerged ticket with an unmerged dependency. Nothing asserts that `unparsed`, `pending`, `ready`, `stopped`, `intake`, `box`, and `reject_queue` are preserved or that their rendering is unchanged. Nothing asserts that the dataclass gained exactly `box_activity`, `tombstone_digest`, and `scorecard`. Nothing asserts the rendered scorecard block. (paved road: Add tests that: (a) build tickets on disk with a confirmed ticket whose declared dependency is unmerged and assert `status.blocked`; (b) assert every preserved field's value and its exact `render()` section text for a representative fixture; (c) assert `[f.name for f in dataclasses.fields(Status)]` equals the preserved twelve followed by exactly the three additive fields; (d) assert that `render()` includes the `render_report(scorecard)` lines when a scorecard is present and omits them when it is absent.)
