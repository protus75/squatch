---
id: tombstone-000107
kind: tombstone
link: decision-000095
reopen_after_days: 30
message: box-000107-45249a6c
---
decision-000095 already covers the section 6 cwd gap for read-only surfaces and reaches the same resolution. The merged Driver passes `worktree=None` to every non-writing surface (squatch/driver.py:126). That makes `CliClient` fall back to its configured checkout cwd (squatch/providers.py:398, :425). specs/review.md also renders the candidate branch's merge-base diff into the prompt as a data block and has the reviewer judge that diff alone. So Review already runs the way the message says the baseline eval does: at the checkout root, with no worktree, reading only a rendered diff. No code ticket is needed. The only remaining gap is one line of plan prose in section 6, and decision-000095 already gave that to the operator. This message adds nothing new except a note that the eval baseline matches the wiring, which supports that decision's operator action without changing it.
