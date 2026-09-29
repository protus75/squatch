---
verdict: snag
reviewed_sha: 6e9824796910b17a6c6118c528dd5bfa4edc7aa8
produced_by_spec_version: '1.0'
produced_at_sha: 6e9824796910b17a6c6118c528dd5bfa4edc7aa8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The resolver move, the gate's use of hostfiles.classify, the marker refusal, and the merge-time rerun wiring all meet the ticket. One defect: the gate only works when the target repo is squatch itself, so on a host repo that has adopted the managed block it crashes and blocks every merge.

## Findings
- correctness_review at squatch/gates.py:34: `_branch_core` always reads `workspace / 'squatch' / 'hostfiles.py'`. squatch merges into host repos as well as itself (Merge._repo / worktree is the target repo, and Phase 6 runs merge against `hosts/fixture/`). A host worktree has no `squatch/hostfiles.py`. So once a host's CLAUDE.md or AGENTS.md contains `squatch:core` text, `read_text()` raises FileNotFoundError. `run_gates` turns that into a crashing-gate failure, which hard-fails every merge in that host. The paved road (`squatch core` then commit) cannot clear it, so the hold has no release. It also lets a host branch that plants its own `squatch/hostfiles.py` choose the template its conduct files are checked against. I'm not certain the plan limits 'fresh branch-version render' to the self-build case, but as written the gate cannot pass in any adopted host repo. (paved road: Take the template from the right source for each target. When the target repo is the engine repo, read the candidate branch's CORE from the branch. Otherwise use the engine's own `hostfiles.CORE`, for example by passing the template source into `CoreDrift` from `Merge`, which knows whether the target is itself. Add a test in tests/test_gates.py or tests/test_hostfiles.py: a workspace with an adopted CLAUDE.md and no `squatch/hostfiles.py` gets a pass/fail verdict from `classify`, not a crash.)
