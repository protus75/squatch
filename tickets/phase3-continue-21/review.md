---
verdict: snag
reviewed_sha: a7493f0095a917d9be8c6a8d912e3105179c90e3
produced_by_spec_version: '1.0'
produced_at_sha: a7493f0095a917d9be8c6a8d912e3105179c90e3
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The previous snag is fixed: new-path owners now come from the scope fences, the successor ownership YAML and a regex over the phase3-exit ownership prose. One gap remains in criterion 3: the downstream edge and tier phrase checks are not tied to the seed they describe, so phase3-exit's dependency on soak-run is not actually pinned.

## Findings
- correctness_review at tests/test_seeded_phase3_21.py:189: Criterion 3 requires the test to pin downstream edges and tiers. The phrase list checks "depends on `soak-run`" and "medium/medium" as bare substrings of the phase3-continue-22 Scope in. Both phrases already appear in the sentence about `phase3-continue-23` ("`phase3-continue-23` depends on `soak-run`, is medium/medium"). So if the continuation ticket dropped or changed phase3-exit's dependency on soak-run, the test would stay green. The same problem applies to soak-run's medium/medium tier and to phase3-continue-23's own edge: neither is tied to its stem. Only "KNOWN-HARD high/high" and "`soak-run` depends on `daemon-soak-runner`" are pinned to a specific seed. (paved road: Use the same technique as the exit-ownership regex. Anchor each edge and tier to its stem with whitespace-tolerant regexes over the phase3-continue-22 Scope in: `soak-run` depends on `daemon-soak-runner`,\s+is medium/medium; `phase3-continue-23` depends on `soak-run`,\s+is medium/medium; and `phase3-exit`.*?depends on `soak-run`,\s+is\s+KNOWN-HARD high/high (re.S). Then remove the bare "depends on `soak-run`" and "medium/medium" substring checks.)
