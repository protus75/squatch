---
id: tombstone-000061
kind: tombstone
link: config-gate-code-vocab
reopen_after_days: 30
message: box-000061-3bfca926
---
This duplicates the open ticket config-gate-code-vocab. The message says that `run_gates` (squatch/gates.py:178) quietly ignores a severity key outside GATE_CODES when it merges `{**SHIPPED_GATE_SEVERITY, **(severity or {})}`, so a misspelled `review.gate_severity` entry is never flagged. Every severity map that reaches `run_gates` starts from `config.review.gate_severity`: diagnose.py:128, stages.py:648 and :941, driver.py:155 through serve.py:225, and merge.py:331. The only thing layered on top is the ticket's gate-bypass codes, which are forced soft. config-gate-code-vocab's Goal already refuses the load with a ConfigError that names the dotted path when a `review.gate_severity` key is not in GATE_CODES, and it adds a test for a misspelled key. Refusing bad keys when the config is loaded is the section 7 behaviour of treating an unknown code as a config error, and after that `run_gates` never sees an out-of-vocabulary key from config. A second check inside `run_gates` would be a parallel validation path, which the no-dual-path law rules out. Reopen if config-gate-code-vocab is dropped or merges without covering `gate_severity` keys, or if a severity source that does not come from config reaches `run_gates`.
