---
verdict: snag
reviewed_sha: 8ca45a439c7f148f577610d96a67eacec7e4e7c5
produced_by_spec_version: '1.0'
produced_at_sha: 8ca45a439c7f148f577610d96a67eacec7e4e7c5
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The intake, caps, custody, triage and serve wiring meet every acceptance criterion, stay inside the fence, and pass all checks. One defect remains: host-supplied log excerpts and report text are written into durable Box custody without passing through the configured secret redactor.

## Findings
- correctness_review at squatch/inbox.py:125: Inbox writes host-captured text into durable Box custody without redaction: `report.log_excerpt` (through `store_evidence` and `_detail`), plus `summary` and `signature`. From there it is rendered into the triage and author prompts, and can be copied into a committed ticket. The engine rule says configured secret values are redacted from every captured stream at the write seam. `Serve.run` already builds a `Redactor` next to the `Inbox` construction, but never passes it in, so a configured secret in a host log line would be stored verbatim in the persistent Box record. I'm not certain host excerpts carry configured secrets in practice, but nothing prevents it and this is the only unredacted captured-stream sink the diff adds. (paved road: Give `Inbox` a `redact: Redactor` parameter, passed from `Serve.run` (squatch/serve.py) where `redact` is already in scope. After metadata validation and the byte-cap checks, redact `log_excerpt`, `summary` and `signature` before calling `store_evidence`/`enqueue`. Add a `tests/test_inbox.py` case proving a configured secret in `log_excerpt` does not appear in the stored Box message.)
