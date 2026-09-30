---
id: decision-000003
kind: decision
link: box-000003-c0d156cd
reopen_after_days: 180
message: box-000003-c0d156cd
---
No action. The extra `.pytest_cache/` entry in `.gitignore` is harmless and costs nothing to keep. Removing it would be a ticket whose only effect is cosmetic, with no change in behavior, and the anti-bloat law weighs against spending pipeline capacity on that. Keeping the line explicit also means the cache stays ignored when a cache dir is created without its inner `.gitignore`, for example after a partial deletion or with a pytest version or plugin that does not write one. No open or merged ticket covers this, so there is nothing to tombstone against. Reopen only if a `.gitignore` hygiene or managed-block pass touches that file anyway.

Evidence: Box message box-000003-c0d156cd (origin bootstrap-ingest) flags the line as redundant. It reports no failure, drift, or wrong behavior. No rendered open or merged work mentions .gitignore or .pytest_cache, and the decision registry is empty.
