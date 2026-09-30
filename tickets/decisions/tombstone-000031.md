---
id: tombstone-000031
kind: tombstone
link: seams-kill-poll-flake
reopen_after_days: 30
message: box-000031-b3e81571
---
This duplicates the open ticket seams-kill-poll-flake. The message makes two points. First, test_cancellation_routes_through_the_same_kill (tests/test_seams.py:145) now pins the group kill with a grandchild pid marker. Second, it uses the same fixed 0.2 s sleep as the timeout test, so the polling fix should apply to both. The file confirms both tests sleep a fixed 0.2 s (tests/test_seams.py:140 in test_timeout_kills_the_whole_group, :163 in test_cancellation_routes_through_the_same_kill). seams-kill-poll-flake's Goal already names both tests. It replaces the single fixed-sleep check in each with one shared polling helper that retries os.kill(grandchild, 0) until ProcessLookupError, with a few-second deadline. The grandchild-marker pin is a fact about the tests as they stand, and it asks for no new work. Reopen if seams-kill-poll-flake is dropped or merges without covering the cancellation test.
