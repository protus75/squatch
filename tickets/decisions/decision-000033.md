---
id: decision-000033
kind: decision
link: box-000033-d955dbe7
reopen_after_days: 90
message: box-000033-d955dbe7
---
No action. The in-place write the message describes is real and deliberate, but it is already documented at the one place a reader would look, and the lint the message worries about does not exist. `Lockfile.acquire` in squatch/lockfile.py (lines 76-84) writes the holder record with `os.ftruncate` plus `os.write` on the flocked descriptor. A comment directly above that code gives the reason: the flock lives on the inode, and the seam's temp-and-rename would swap in a fresh inode that is not locked. The plan does not have an 'all writes go through the seam' rule that this write breaks. It mentions atomic replace through the filesystem seam only for specific writers (for example the one atomic replace in `migrate-config`). No merged or open ticket builds a lint that sends every write through the seam. Adding an exemption entry to a seams inventory for a lint nobody has built is the speculative metadata the anti-bloat law rules out. No rendered ticket or decision covers lockfile write paths, so a tombstone would be wrong. Reopen if a ticket proposes a check that requires writes to go through the filesystem seam. That ticket must allowlist the lockfile's in-place write in the same change, and cite lockfile.py:76-78 as the reason.

Evidence: squatch/lockfile.py:76-84 (comment giving the reason, then ftruncate/write on the locked fd). The `Filesystem` protocol is at squatch/seams.py:38 and the atomic os.replace at seams.py:197. SQUATCH_PLAN.md names the filesystem seam's atomic replace only for particular writers such as migrate-config (line 1286), and has no rule that every write must use it. No open or merged ticket in the rendered projections adds a lint that sends all writes through the seam.
