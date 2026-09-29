---
verdict: snag
reviewed_sha: c43f66c0efd194ace260b8dd5f3ce5c9fe7b69b4
produced_by_spec_version: '1.0'
produced_at_sha: c43f66c0efd194ace260b8dd5f3ce5c9fe7b69b4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The renderer in squatch/hostfiles.py and its tests meet the renderer criteria, but the `core` verb is only a stub. It prints a fixed string and never calls the renderer, and no later seed in the plan's Phase 6 registry owns `squatch/__main__.py` to connect it.

## Findings
- correctness_review at squatch/__main__.py:129: `_core` does not import or call `squatch.hostfiles`. It prints the fixed line 'core: managed conduct-file renderer is available' and returns 0 no matter what state the host is in. Its docstring says it exposes the renderer, but the code never invokes it. The plan's closed CLI vocabulary (the 'A sprawling CLI' anti-goal) defines `core` as the operator and new-host invocation of the one `squatch:core` bootstrap renderer. The ticket says to 'Register the `core` CLI', and this is the only Phase 6 seed that owns that registration: `core-drift-activation` does not fence `squatch/__main__.py`, and `migrate-config` adds only its own verb. As merged, the verb is a no-op that reports success, and nothing in the plan ever connects it to the renderer. I am fairly but not fully confident this is a defect. If the plan authors meant `core` to be a dormant placeholder, the plan should say so and this finding drops. On this reading, though, the fixed string tested in tests/test_cli.py pins a placeholder, not the verb's contract. (paved road: Have `_core` call `hostfiles.render` on the conduct file(s) the verb targets. Read and write only through the filesystem seam, use no Git or commit operation, return EXIT_OK when the file is rendered or already current, and map `ManagedBlockRefusal` to the engine-plane refusal exit (2) with the refusal message. In tests/test_cli.py, cover first adoption on a file with no markers, a byte-identical re-run, and the refusal exit on malformed marker text. If the plan really intends a dormant stub, fix the plan first and state that the verb is a placeholder there, rather than printing a claim that the renderer is available.)
