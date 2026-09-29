---
verdict: snag
reviewed_sha: 8318abfaf39648340c9f2b22d17a65985e8c5c31
produced_by_spec_version: '1.0'
produced_at_sha: 8318abfaf39648340c9f2b22d17a65985e8c5c31
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Intake, bounds, custody, triage and serve wiring meet every acceptance criterion and stay inside the fence, and checks are green. However, Inbox writes several host-supplied fields and the replay bytes to durable Box custody without redaction, and its broad OSError catch permanently quarantines valid reports when Box has an engine-side write failure.

## Findings
- correctness_review at squatch/inbox.py:104: Only summary, signature and log_excerpt are redacted. app_commit, app_version, implicated_paths and replay_file go verbatim into Evidence and into `_detail`, and both are written to the Box message JSON. A configured secret value in any of these fields is therefore written unredacted to durable storage. The replay bytes are also stored as-is by `store_evidence`, with no redaction or secret check. The tests only put secrets in summary, signature and excerpt, and the replay fixture is always `{}`, so the gap is not covered. (paved road: Apply `self._redact` to every host-supplied text field in the model_copy update (app_commit, app_version, each implicated_path). For the replay bytes, fail closed: reject the report if any configured secret value appears in them (rewriting the bytes would break the sha256 custody check). Add a test that puts a secret in app_version and in the replay, then asserts no file under box.dir contains it.)
- correctness_review at squatch/inbox.py:89: `consume` catches every OSError/ValueError from `_consume_one`, including failures inside `self._box.store_evidence` and `self._box.enqueue`, such as a full disk or a failed Box write. These are engine-side, transient custody failures, but the loop renames the host's valid report to `.rejected`, which is terminal. The evidence is quarantined as if the host had sent a bad report, and no automatic retry happens. (paved road: Convert only host-attributable failures to ReportError: metadata problems and replay stat/read errors, which already are. Catch only ReportError in `consume`. Let Box write errors propagate so the report stays `*.report.json` and is retried on the next pass, matching how the failed-rename path already behaves.)
