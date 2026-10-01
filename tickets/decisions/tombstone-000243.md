---
id: tombstone-000243
kind: tombstone
link: suggestion-box
reopen_after_days: 90
message: box-000243-66e2b343
---
suggestion-box is merged and appears in merged_work, so the fence gap this message predicted never blocked its dispatch. The Git wrapper verb the message said was missing now exists. `Git.git_common_dir` (squatch/git.py:68-69) runs `rev-parse --git-common-dir` as its own argv verb, separate from `rev_parse` (--verify), so nothing reaches into `Git._run`. tests/test_git.py:109-111 and :324-336 pin it, covering both a main checkout and a linked worktree resolving to the shared `.git`. The suggestion-box module entry calls it at squatch/box.py:473, and squatch/audit.py:206 reuses it. Fencing git.py or rewording the seed now would only add change history for finished work, and the message gives no evidence (origin bootstrap-ingest), so under D10 that edit would be speculative. Reopen if suggestion-box is regenerated and its fence review flags the squatch/git.py or tests/test_git.py edits as out of scope, or if its Implement attempt parks on a fence wall over resolving the instance checkout.
