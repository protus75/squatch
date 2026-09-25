# squatch

squatch is a continuously running orchestration engine that authors and runs tickets against host project repos, including itself: it drafts the ticket set for a feature, wires dependencies, runs implement -> check -> review -> merge, harvests failures, and files follow-ups.
Two rule planes. **Engine plane** (this repo, squatch-owned): HOW work runs. **Host plane** (each target repo): WHAT to build; it enters the pipeline only as rendered data and is never engine-edited.
Design goals, in priority order: simple and robust over feature-rich; automated with small, enumerated human touchpoints; a continuous queue, never batches; one pattern for every stage, gate, and handoff; every failure path designed.
Judgment goes in LLMs; verdicts go in scripts.

**Read first: `SQUATCH_PLAN.md` is canonical.** This file is the curated subset of `CLAUDE.md` for non-Claude agent CLIs; `CLAUDE.md` is canonical on conflict, and a rule change touches both in the same change.

## Engine conduct

- **Pure Python.** No shell scripts, no `shell=True`, no string-assembled commands; external binaries only through argv wrapper modules; the squatch venv only. [D1]
- **Build the simplest thing that satisfies the ticket.** No speculative features, gates, config knobs, or metadata; every addition cites the incident that earned it. [goal 1, D10]
- **No dual-path code.** No compat shims, deprecation layers, or defensive parallel paths. Rename in place, update every call site in the same change; recover by revert. [section 2]
- **Fail closed.** Allowlists and closed vocabularies, never denylists; every prohibition and every gate finding ships a paved road. [sections 2, 7]
- **Files + journal are the source of truth.** Derived views (status, backlog, ledger, scorecard) are projections: never hand-edit one or cite one as authority. [D3]
- **Generated files are render targets, never write targets.** `README.md` and `bootstrap/conductor.py` extract from the plan's appendix sentinel blocks; `CLAUDE.md` and this file are authored from plan section 17. A change edits the plan and reruns the generator, never the rendered file. [section 1]
- **The plan is the seed.** A plan defect is fixed in the plan, then regenerated from it. Hand-edit a ticket or code file ONLY for a defect provably not the plan's, OR under the blocking-defect fast path (plan edited and committed FIRST, then the minimal congruent fix), and never before the plan's status is determined. [sections 1, 19]
- **All git through `git.py`.** Argv lists, dir-pinned; worktree cleanup is `worktree remove` + `prune`, never bare `rm -rf`; no `gh`, no PRs in the loop. [section 10]
- **Second problems are filed, never folded in.** An adjacent bug, refactor itch, or pre-existing red goes to the Suggestion Box, not the current diff; a pre-existing failure is verified on the base commit first, then filed. [section 11]
- **Read before write.** No command, claim, or test is written until the artifact that owns that fact has been read. [section 13]
- **Ticket frontmatter is minimal.** Only fields the scheduler, a gate, or the authoring/triage policy reads; ordering lives in `depends` and `priority`, never in prose. [section 13]
- **Use the injectable seams.** Clock, process exec, filesystem, and notifications go through the seams, never called raw in engine code. [section 15]
- **Executed work is fenced, not jailed.** v1 does not sandbox executed code; never rely on its goodwill, and never pass a provider key to a process that does not need it. [section 16]
- **The journal is the record, never a debug log.** Diagnostics go to the engine log and attempt spools; configured secret values are redacted from every captured stream at the write seam. [section 6]

## Working conduct

- **Comments explain why, not what.** Comment only invariants, hazards, and deliberate-looking-wrong choices; match surrounding density. [section 17]
- **Git safety.** Stage and commit only files authored in this change, by explicit path; never a tree-wide destructive verb (`clean`, `reset --hard`, `checkout -- .`); never push or remote-mutate. [sections 10, 13]
