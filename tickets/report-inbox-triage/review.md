---
verdict: snag
reviewed_sha: f7446e1d80c5bc65bfa498aa2017b3a3c7275104
produced_by_spec_version: '1.0'
produced_at_sha: f7446e1d80c5bc65bfa498aa2017b3a3c7275104
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The intake, custody, triage and serve wiring meets every acceptance criterion and stays inside the fence, and the check report is green. One logic defect remains: the metadata byte cap rejects valid version-1 reports whose log excerpt is within 64 KiB but grows when JSON-escaped.

## Findings
- correctness_review at squatch/inbox.py:16: METADATA_LIMIT is LOG_EXCERPT_LIMIT + 16 KiB (80 KiB), and `_metadata` checks it against the size of the raw JSON file. `log_excerpt_bytes` counts the decoded UTF-8 excerpt, not its JSON-encoded form, and JSON escaping can multiply its size: `"` and `\` take 2 bytes, control characters and ANSI escapes (ESC -> `\u001b`) take 6 bytes per input byte, and non-ASCII text under the default ensure_ascii takes up to 12 bytes per 4-byte character. A schema-valid report with, say, a 60 KiB excerpt full of quotes or ANSI color codes (common in logs) goes over 80 KiB on disk. `_metadata` then rejects it as oversized metadata and moves it to `.rejected`, even though its excerpt is within the 64 KiB cap. So the intake rejects evidence the version-1 schema allows, and a test with a plain ASCII excerpt cannot catch it. (paved road: Size METADATA_LIMIT from the worst-case JSON expansion of an excerpt that is exactly at the cap, e.g. `6 * LOG_EXCERPT_LIMIT + 16 * 1024`; that covers `\uXXXX` escapes, and a 4-byte character written as a surrogate pair uses 12 bytes for 4 input bytes, which is the same 3x ratio as 6 bytes per 2. Keep the pre-parse stat check as the memory bound. Add a test_inbox.py case where an escape-heavy excerpt at LOG_EXCERPT_LIMIT is filed, not rejected.)
