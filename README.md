# squatch

squatch is a continuously running orchestration engine that authors and runs
tickets against host repos, including itself. This README is GENERATED from
SQUATCH_PLAN.md (the `# BEGIN_README` block in its appendix) -- edit that block,
never this file. SQUATCH_PLAN.md is canonical for everything: read section 0
(cold start, prerequisites, the conductor and its rungs, the self-hosting
handoff) first, and run its one-time cold-start paste to seed the repo, venv,
and deps before any command below.

The lifecycle is four commands, run in order:

    python3 bootstrap/conductor.py            # bootstrap: Phase 0 then Phase 1, gated per deliverable
    python3 bootstrap/conductor.py --auto     # same, unattended (no verdict pauses)
    uv run python -m squatch drain             # after Phase 1: ONE drain self-hosts Phases 2-6 to quiescence
    uv run python -m squatch serve             # cutover: start the continuous daemon on host work (after GO is recorded)

Once `serve` is running, control it with `kill` / `pause` / `resume`; `status`
and `doctor` inspect at any time. Section 18 lists every verb; section 13
touchpoint 7 is the GO/cutover gate `serve` waits behind.
