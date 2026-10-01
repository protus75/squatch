---
id: tombstone-000239
kind: tombstone
link: suggestion-box
reopen_after_days: 90
message: box-000239-3e7f09ec
---
The message asks the plan to name the invocation for the one-time `bootstrap/suggestions.md` ingestion. That work is already merged in suggestion-box. Its rendered Goal covers ingesting `bootstrap/suggestions.md` once as the box's first messages and deleting the file in the same diff, and both have happened: the file is gone from `bootstrap/`, and this message has origin `bootstrap-ingest`. The entry point is also no longer an unnamed surface. `squatch/box.py:485` defines the `ingest` subparser with its `__main__` guard at :537, and plan section 19 (SQUATCH_PLAN.md:1573) names `python -m squatch.box ingest` as the standalone entry, including how it fails closed on a tombstone match without a journal callback. Adding the entry to section 12 or 19 as a bootstrap step now would describe a finished step, which section 17 treats as change history. The message gives no evidence, so under D10 that edit would be speculative. Reopen if suggestion-box is regenerated and its fence review flags `python -m squatch.box ingest` as an invented CLI surface, or if section 18's closed verb list is changed in a way that leaves out the module entry.
