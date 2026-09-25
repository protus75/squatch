---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- invariant-auditor

## Context
- squatch/stages.py
- squatch/artifacts.py
- squatch/runner.py
- squatch/drain.py
- squatch/merge.py
- tests/test_drain.py
- tests/test_terminal.py

## Plan contract
- section 19

## Goal
The shakeout battery's report lane exists before any group writes to it: `shakeout-report.json` has a closed schema registered among the lane writer's KNOWN artifacts in `squatch/stages.py`, `eval/shakeout/` owns the bench that drives the production composition under the fake LLM, the ordered group registry, the runner that machine-produces the cumulative report into a worktree OUTBOX with the double-gate re-confirmation of every prior group's entries, and a `check` mode the phase exit reads with; no group is registered yet.

## Why
Section 19 fixes the battery's custody: entries are MACHINE-PRODUCED byte-for-byte to the worktree OUTBOX by the group runs -- a hand-authored or relabelled-green entry is the false-green class the battery exists to catch -- lifted by the ONE existing stage-terminal lift path of section 10 (whose owner, `squatch/stages.py`, this deliverable therefore fences), each later group re-confirming every prior group's entries before appending its own, the cumulative copy resting in the last group's ticket dir. Section 10 says the lane writer validates artifacts it KNOWS, so the report's schema is registered there and an invalid report never reaches main. Section 15 rung 4 names the bench: fake-agent simulation driving whole pipelines through the injected seams with the invariant auditor as the pass condition, so a member is green only when its discriminating observable matched AND the auditor is green over that member's own journal. Section 9's fence law binds fixtures like features: this lane ticket owns the harness and the registry; each group ticket owns exactly the module it pins, its test file, and its member module.

## Scope in
A new module `squatch/shakeout.py` owning the schema: `REPORT_NAME` = `shakeout-report.json`; `Entry` (closed: `member` -- `<group stem>.<name>`, `group`, `fault` -- the planted fault, `observable` -- the single discriminating terminal, event, or artifact field, `expected`, `observed` -- stable code-only strings, `detail` -- the artifact path pattern carrying the human-readable detail, `producing_run` -- `<bench stem>/<run_seq>`, deterministic under the injected clock and fake, `auditor` in `green | red`, `green` -- true exactly when `observed == expected` and `auditor == green`); `ShakeoutReport` (closed: `schema_version` 1, `produced_at_sha`, `groups` -- the ordered group stems, `entries`); `dumps(report)` -- canonical JSON, sorted keys, two-space indent, trailing newline, so equal entries are equal bytes. `squatch/stages.py` gains `KNOWN_ARTIFACTS`, a mapping of outbox file name to validator holding `REPORT_NAME -> ShakeoutReport.model_validate_json`, and `_lift` validates every outbox file whose name is registered BEFORE writing it into the canonical dir: an invalid file is not lifted and the lift raises a typed `LiftRefused` the stage layer turns into the run's non-ok terminal `invalid_artifact` with a finding naming the file and the schema error (fail closed; nothing else about the lift changes). A new package `eval/shakeout/` owning the harness: `bench.py` -- `Bench.make(tmp, *, fake, clock)` builds a real git checkout with a `config.yaml` shaped like this instance's (one `cli` provider, the shipped caps), a `FakeLLM` behind `LLMEffect`, an injected clock, and the PRODUCTION `Runner`, `Drain`, and `compose_pipeline` composition; `bench.write_ticket(stem, text)`, `bench.commit(paths, subject)`, `bench.drain() -> int`, `bench.run(stem) -> int`, `bench.events()`, `bench.terminal(stem, run_seq)`, `bench.artifact(stem, name)`; `registry.py` -- `GROUPS`, an ordered tuple of `(group stem, member module)` pairs, EMPTY here, and `Member(name, fault, observable, expected, detail, run: Callable[[Bench], str])`; `__main__.py` -- `uv run python -m eval.shakeout run --outbox <dir> [--prior <report>]` runs every registered group in order, each member on a fresh `Bench`, records `observed` and the auditor's verdict over that bench's journal (`squatch/audit.py`), builds the cumulative report, and when `--prior` is given asserts the DOUBLE GATE: for every group but the last registered, the freshly produced entries equal the prior report's entries for that group byte-for-byte (`dumps` of the entry lists), else it writes no report, prints the first differing member, and exits 1; then writes `<outbox>/shakeout-report.json` and exits 0 when every entry is green, 1 otherwise (the report is written either way so the failed Check carries it); `uv run python -m eval.shakeout check <report>` validates the schema, requires every REGISTERED member present and green, prints one line per member, and exits 0 or 1; both exit 2 with a paved road on a refusal. Tests in `tests/test_shakeout.py`: the schema, `dumps` determinism, the lift registration through a fake outbox, the runner over a fixture group registered ONLY inside the test (a passing member, a failing member, a member whose bench journal violates an invariant), the double gate, and `check`. Read `squatch/audit.py` in the worktree (it lands with the `depends`), and read `squatch/journal.py`, `squatch/git.py`, `squatch/seams.py`, `squatch/llm.py`, `squatch/llmeffect.py`, `squatch/config.py`, and `eval/harness.py` there too (kept out of `Context` so the base Implement render clears the section 8 bound with headroom).

## Scope out
No battery member and no registered group: the eight group seeds register themselves. No second lift path, no hand-committed report, no `eval/reports/` copy. No wall-clock soak, no `serve` composition (Phase 3). No change to `checks.json`, `review.md`, `run.md`, or `diagnosis.json` validation beyond the new registry holding one name. No new CLI verb, frontmatter field, config key, cap, or journal event type.

## Scope fence
- squatch/shakeout.py
- squatch/stages.py
- eval/shakeout/
- tests/test_shakeout.py
- tests/test_stages.py

## Acceptance criteria
- In `tests/test_shakeout.py`, `Entry` refuses an `auditor` outside `green | red`, a `green` of true when `observed` differs from `expected`, and an unknown field; `ShakeoutReport` refuses `schema_version` 2; `dumps` of two reports built from the same entries in the same order is byte-identical.
- In `tests/test_shakeout.py`, `KNOWN_ARTIFACTS` in `squatch/stages.py` maps `shakeout-report.json` to the report validator, a lift over an outbox holding a valid report commits it to `tickets/<stem>/shakeout-report.json`, and a lift over an invalid one commits nothing under that name and the run ends `invalid_artifact` with a finding naming the file.
- In `tests/test_shakeout.py`, `run` over a test-registered fixture group with one passing member, one whose observable mismatches, and one whose bench journal carries a planted duplicate terminal writes a report with exactly those three entries, `green` true only for the first, `auditor` `red` only for the third, and exits 1; with the failing members removed it exits 0.
- In `tests/test_shakeout.py`, `run --prior` over a prior report whose entry for a prior group differs by one byte writes no report, prints that member, and exits 1; over an identical prior report it appends the last group's entries after the prior ones and exits 0.
- In `tests/test_shakeout.py`, `check` exits 0 over a report where every registered member is green, 1 when a registered member is missing or red, and the `Bench` drives a two-ticket drain through the production `Runner` and `Drain` to quiescence with `bench.terminal` reporting `merged` for both.
- `uv run python -m eval.shakeout check --help` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_shakeout.py -q
uv run pytest tests/test_stages.py -q
uv run python -m eval.shakeout check --help
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the outbox lift in `squatch/stages.py` cannot validate a registered name without a second lift path, if the production `Runner`, `Drain`, and `compose_pipeline` cannot be composed over a temp checkout with a `FakeLLM` the way `tests/test_drain.py` does, if `squatch/audit.py` as landed cannot audit a bench journal in-process, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 75m
- stuck: 150m
