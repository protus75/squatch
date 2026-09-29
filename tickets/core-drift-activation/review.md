---
verdict: snag
reviewed_sha: 82bf6235c8f1007dbd425d0ac3ab8f86d64533ef
produced_by_spec_version: '1.0'
produced_at_sha: 82bf6235c8f1007dbd425d0ac3ab8f86d64533ef
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The resolver move, gate wiring and merge-time rerun are correct, and the resolver is shared through `providers.conduct_files`. Two problems block approval: the tests never show the gate refusing malformed markers, which is a stated acceptance criterion, and the gate compares against the running engine's CORE, not a render from the branch's own version.

## Findings
- correctness_review at tests/test_hostfiles.py:95: Acceptance criterion 2 requires `tests/test_hostfiles.py` to prove the gate refuses malformed marker forms. The only new gate-level test covers the drifted case. The existing marker-refusal tests call `render`/`classify` directly, so nothing shows that `CoreDrift.check` returns a hard `fail` finding for a malformed, partial, duplicate or stray marker. A gate that passed or skipped the `refused` state would not be caught, and `Definition of rejected` names permissive marker handling explicitly. (paved road: Add a parametrized `CoreDrift(config).check(...)` test in `tests/test_hostfiles.py` over the malformed, partial, duplicate and stray marker fixtures. Assert `verdict == 'fail'`, a single `core_drift` finding on `CLAUDE.md`, and that the file bytes are unchanged.)
- correctness_review at squatch/gates.py:93: The ticket and plan section 20 require a comparison with a fresh BRANCH-VERSION render. `CoreDrift` calls `hostfiles.classify(content)` with the default `CORE` of the engine process doing the merge, which is the main/engine version, not the candidate branch's `squatch/hostfiles.py`. When a self-hosted ticket changes `hostfiles.CORE` and re-renders `CLAUDE.md`/`AGENTS.md` in the same diff, the gate compares against the old template and reports `drifted`, blocking a correct change. The reverse case lets stale files through. I am not certain the plan means the branch's template; if 'branch-version render' only means rendering the branch's file content, this finding is void, but the implementation should say so. (paved road: Render against the template the candidate branch carries, for example by loading `CORE` from the branch's `squatch/hostfiles.py` without importing branch code into the engine, and pass it as `classify(content, core)`. Otherwise, get the premise clarified in the plan before merging. Add a test where the branch changes CORE and re-renders consistently, and assert the gate passes.)
