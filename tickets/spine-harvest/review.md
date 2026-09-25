---
verdict: snag
reviewed_sha: 4a54c663cfff5faaab74d783105d5cc67dc12f1c
produced_by_spec_version: '1.0'
produced_at_sha: 4a54c663cfff5faaab74d783105d5cc67dc12f1c
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The terminal handler, reconcile harvest, seam return type and prior-attempts render all meet the ticket, but the spool-tail harvest copies unreviewed diff content to main after a Review-stage non-ok terminal. That breaks the ticket's 'no content of the diff in any harvested file' rule.

## Findings
- correctness_review at squatch/harvest.py:49: `extract` stores the last TAIL_CHARS (8000) characters of every spool file. The Driver names spool files by call sequence only (`001-prompt.md`, `001-response.md`), so after a Review verdict of snag or rma, `001-prompt.md` holds the Review prompt. That prompt embeds the whole candidate diff in its `diff` data block. After that block come only the check report and about 2-3k characters of spec text (`specs/review.md` is 4.6 KB), so an 8000-character tail includes the last several KB of the unreviewed diff. `harvest.json` is then committed to main. This violates Scope out ('No content of the diff in any harvested file') and the Why ('the unreviewed diff never enters the ticket spec'). The new `test_harvest.py` only covers a `gate_failed` at Check, where no Review prompt exists, so the leak is untested. I am fairly but not fully sure the ticket intended to keep these tails; the conflict with 'every file in the spool dir' may be the ticket's own tension, but a fix inside the fence exists. (paved road: Before tailing a spool file in `extract`, remove the body of any `diff` data block: replace everything between the diff block's open and close markers (built from DATA_MARKER, not spelled raw) with a placeholder such as `(diff elided: N chars)`. Then take the TAIL_CHARS tail. Add a `tests/test_harvest.py` case where Review answers snag over a diff with a unique source line, and assert that line appears nowhere in `harvest.json`.)
