---
verdict: snag
reviewed_sha: e222708ca8c0dcb75cdca2c286cfdefa7f3f82e5
produced_by_spec_version: '1.0'
produced_at_sha: e222708ca8c0dcb75cdca2c286cfdefa7f3f82e5
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The classification, the Driver mapping, the tests and the shakeout member cover every acceptance criterion, and all checks are green. One logic defect: the auth signature is the generic phrase "Not logged in", and it is searched for across the agent's whole stdout event stream, so an ordinary failed run can be misclassified as an expired login.

## Findings
- correctness_review at squatch/providers.py:99: `_Adapter.error` sets `failure_class="auth_error"` whenever the case-folded substring "Not logged in" appears anywhere in `out + stderr`. For a codex or claude implement call, `out` is the full JSON event stream, which includes command and tool output the agent produced. Suppose an agent runs `npm whoami` or `gh auth status`, which print "Not logged in", and the call then fails with a non-zero exit or a failed turn for any other reason. That failure is classified as an expired CLI login and tells the operator to re-authenticate. This is the phantom-failure misdirection the ticket exists to prevent, just in the other direction. Both adapters also declare the same generic signature, so the check doesn't identify which CLI failed. I'm not certain of the exact auth-failure text each CLI emits, but matching across the whole stream is too broad either way. (paved road: Match only where the CLI itself reports the failure: for claude, the result event's error text (`parsed.failure`) and stderr; for codex, stderr and the error or turn-failed event message. Don't search the whole stdout transcript. Make each adapter's signature specific to that CLI's actual auth-failure message. Add a test where "Not logged in" appears only in agent command output inside a failed stream and assert `failure_class` is None.)
