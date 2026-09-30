---
id: decision-000017
kind: decision
link: box-000017-c7d64057
reopen_after_days: 90
message: box-000017-c7d64057
---
No action needed. The message is stale. It says the section 6 redaction seam is a later deliverable, but `squatch/redact.py` has shipped, and every `Effects.run` action whose result carries captured subprocess or model text redacts that text before returning it. The `effect_completion` body therefore never holds unredacted captured-stream text. The model call returns `asdict(_scrubbed(task.result(), self._redact))` (llmeffect.py:72). The rebase refusal text goes through `self._redact(...)` (merge.py:343). Verification stdout/stderr, on both the branch and the base, is redacted before it enters the Check or regate invoice (stages.py:379, 406, 434), and regate builds its `Verification` with the redactor (merge.py:375). The other effect results hold only engine-generated values: commit shas, branch names, the base sha and invoices built from redacted findings (merge.py:345, 417, 437). Adding a second, blanket redaction pass inside `Effects` or `Journal.append` would be a parallel defensive path with no incident behind it, and the no-dual-path and anti-bloat laws rule that out. No rendered stem clearly owns the redaction seam, so a tombstone would mean guessing the link. Reopen if a new `Effects.run` action returns captured subprocess or model text without passing it through the Redactor, or if a configured secret value turns up in any journal segment.

Evidence: squatch/llmeffect.py:72,107-111 (_scrubbed); squatch/merge.py:343 (redacted rebase refusal), 375 (Verification gets redact), 345/417/437 (engine-generated results only); squatch/stages.py:379,406,434 (verification out/err and error detail redacted); Effects.run call sites listed by grep across checkpoint, stages, retro, requisition, notify, merge.
