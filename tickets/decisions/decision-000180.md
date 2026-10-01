---
id: decision-000180
kind: decision
link: box-000180-58fbf962
reopen_after_days: 90
message: box-000180-58fbf962
---
No ticket. The defect the message describes is not in the current file. The module docstring in squatch/runner.py (lines 1-23) has no line over 90 columns. Its longest line is about 78 columns. Every line in the file over 90 columns is code or a string literal, not docstring prose. Later edits have already removed the 102-column line, which dates from the bootstrap ingest window. The only remaining quirk is a ragged wrap: line 12 ends early at "named stem; `drain`" and line 13 continues it. That is cosmetic. It changes no behavior, gate or test, and the plan has no line-width rule for docstrings. Under D10 it does not earn a ticket by itself, and a one-off re-wrap would also churn a generated-from-plan file for no observable gain. No rendered work or decision covers docstring wrapping, so a tombstone would be wrong. Reopen if a line-length or docstring-format gate is added to the plan, or if the runner.py module docstring is found to carry a line over the file's wrap width again.

Evidence: A grep for lines of 91 or more characters in squatch/runner.py matches only code lines (50, 149-150, 176-555), none of them in the docstring at lines 1-23. Reading lines 1-23 shows every line at or under about 78 columns. Lines 11-13 ('...around one / named stem; `drain` / (`squatch.drain`) composes them...') are short-wrapped, not overlong.
