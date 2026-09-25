---
verdict: snag
reviewed_sha: 1a2d58a00e9b1eac136ce4f7c09c9759da324dc2
produced_by_spec_version: '1.0'
produced_at_sha: 1a2d58a00e9b1eac136ce4f7c09c9759da324dc2
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Every acceptance criterion is met, every path is inside the fence, the check report is green, and the instance box holds the 257 ingested lines. Two defects remain: harvest files the worktree run.md's second problems into the box without redaction, and the second-problem parser drops bullets that start with `*`.

## Findings
- correctness_review at squatch/harvest.py:82: `extract` now calls `enqueue_second_problems` on the raw worktree `run.md` (`worktree / TICKETS_DIR / stem / RUN_RECORD`). Each bullet goes verbatim into `summary` and `detail` of a box message, which `Box.enqueue` writes straight into `<state_dir>/box/` through `fs.write`. No redactor is on that path. The same bytes copied into `attempts/<n>/run.md` are scrubbed later, because `lift_ticket_files` receives `redact=self._log._redact` (runner.py:199; stages.py:733/738). The box copy skips that step. So a configured secret that an agent writes into `## Second problems filed` stays in a durable box file that is never deleted. `status` also prints the summary, so the secret reaches the operator's screen. This breaks the rule that configured secret values are redacted from every captured stream at the write seam. (paved road: Scrub the run-record text with the runner's Redactor before parsing, for example by passing `redact` into `extract` and giving `enqueue_second_problems` the redacted text. Add a test that plants a configured secret in a second-problem bullet and asserts it appears in no file under `<state_dir>/box/`.)
- correctness_review at squatch/box.py:196: `enqueue_second_problems` treats a line as a bullet only if it `startswith("-")`. A `* problem` bullet, which is valid markdown and is accepted by `ingest`'s `_LIST_MARKER` in the same module, is silently never filed, so that problem is lost. A citation written as a code span (`` - `box-000001-deadbeef` ``) fails `_BOX_ID.fullmatch` and gets filed as a new suggestion instead of being skipped. The ticket requires one suggestion per non-empty bullet and says `box-` citations are skipped. (paved road: Detect bullets with the same marker regex `ingest` uses (`- `, `* `, `<digits>. `). Strip surrounding backticks before the `_BOX_ID` citation check. Add both cases to `test_enqueue_second_problems_and_empty_section`.)
