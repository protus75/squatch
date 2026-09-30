---
id: tombstone-000023
kind: tombstone
link: decision-000017
reopen_after_days: 90
message: box-000023-504af5cd
---
This duplicates decision-000017, which already records that the section 6 redaction seam has shipped and that captured subprocess text is redacted above `SubprocessExec.run` before it reaches an `effect_completion` body. The other two sinks the message names are covered as well. `EngineLog` scrubs every record through the Redactor before writing it (enginelog.py:35, 49-61). `Spool` is always built with the redactor (stages.py:645, triage.py:201, serve.py:223). The CLI client redacts the prompt spool write, the watchdog event lines and both captured streams right after `SubprocessExec.run` returns (providers.py:438, 451, 460). Verification out/err and attempt-spool bytes are redacted in stages.py:379, 406, 1176 and 1196. Leaving `SubprocessExec.run` verbatim is the intended layering: redaction happens at the write seam, above the process seam. Reopen under decision-000017's conditions: a new captured-stream writer that skips the Redactor, or a configured secret value found in the journal, a spool or the engine log.
