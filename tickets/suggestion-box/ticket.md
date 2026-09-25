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
- spine-diagnosis

## Context
- squatch/runner.py
- squatch/status.py
- squatch/tickets.py
- squatch/git.py
- squatch/seams.py
- squatch/journal.py
- squatch/config.py
- squatch/artifacts.py
- squatch/__main__.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_cli.py

## Plan contract
- section 12
- section 11
- section 13
- section 9

## Goal
The Suggestion Box exists before anything files into it: one durable queue of atomic per-message JSON files under the state dir with signature dedup at enqueue, the decision registry's record model, reader, and ticket-plane writer, harvest enqueuing each run record's second problems, `status` listing box activity, the drain provably never scanning the box, and `bootstrap/suggestions.md` ingested once as the box's first messages and deleted in this ticket's own diff.

## Why
Section 12: one durable queue, one sequential consumer, never a hard-deleted duplicate. Section 11.7: a second problem is filed, never folded into the diff that found it, and harvest is the producer that turns a run record's filed problems into triageable work -- so the mailbox must exist before its first letter, and every later spine seed (the `reject` kill's per-dependent reports, triage, retro) files into it rather than inventing a queue. Section 19 makes the section 0 stand-in this box's first content: `bootstrap/suggestions.md` was the pre-box mailbox every conductor context appended to, and its lines become suggestion-class messages under the gitignored state dir, so the deletion is the repo-visible half of ingestion and rides this code lane, never a ticket-plane commit. Section 12's era split is a test here, not a rule in prose: the bootstrap drain never scans the box, and the consumer (`squatch triage`, a later seed) is the only reader.

## Scope in
A new module `squatch/box.py` owning the queue. `MESSAGE_CLASSES` is the closed set `suggestion | failure_report | override_report | retro_finding | bug_report`; `STATUSES` is the closed set `pending | authored | tombstoned | decided`; `BOOTSTRAP_ORIGIN` = `bootstrap-ingest`. `Message` is a closed pydantic model with its own `schema_version` (1): `id` (`box-<seq>-<sig8>`), `seq`, `signature` (64 hex), `message_class`, `summary`, `detail` (the reason or body text, data never prose), `origin` (the producing stem, or `bootstrap-ingest`), `stage`, `outcome`, `run_seq` (each nullable), `enqueued_at` (the clock seam, rendered as the journal renders `ts`), `status`, `resolution` (null, or `link` + `note` + `resolved_at`, written by the consumer), and `reports` (arrivals collapsed onto this record, 1 at enqueue -- the count the Phase 3 breaker and the Phase 5 K-reopen read). `signature(message_class, origin, stage, outcome, reason)` is sha256 over those five joined, the reason normalized per section 12: every whitespace-delimited token containing `/` dropped, every digit run dropped, whitespace collapsed to single spaces, then stripped; a bootstrap line signs over (`suggestion`, `bootstrap-ingest`, its normalized text). `Box(state_dir, *, fs, clock)` owns `<state_dir>/box/`: `enqueue(...) -> Enqueued(id, duplicate)` writes `<seq:06d>-<sig8>.json` through the filesystem seam, `seq` one past the highest on disk, refusing to overwrite an existing name; an arriving signature already on disk (any status) is never a second file -- its `reports` is incremented by atomic replace and its id returned with `duplicate` true; `pending()` returns pending messages in seq order; `get(id)`; `resolve(id, *, status, link, note)` atomically replaces the file, refusing a status outside `STATUSES` or a message not `pending`. `enqueue_second_problems(box, run_record, *, stem, stage, outcome, run_seq) -> list[str]` files one `suggestion` per non-empty bullet under the run record's `## Second problems filed` (a bullet that is itself a `box-` id is a citation, not a problem, and is skipped), origin the stem, `detail` the bullet text. `ingest(box, path) -> Ingested(filed, duplicates)` files one `suggestion` per non-empty line of the file, origin `bootstrap-ingest`, `summary` the line with a leading list marker (`- `, `* `, `<digits>. `) stripped, `detail` the raw line -- idempotent by signature, so a second ingestion files nothing new. The module entry `uv run python -m squatch.box ingest <file>` performs it against the INSTANCE state dir, resolved through `squatch/git.py`: the checkout whose `.git` `git rev-parse --git-common-dir` names (a worktree resolves to its parent checkout, the main checkout to itself), then that checkout's `config.yaml` `state_dir` -- exit 0 with the counts printed, exit 2 with a paved road on a missing file or an unresolvable checkout; it takes no lock, because the box is neither the journal nor git (section 12's atomic per-message file is the whole durability contract). A new module `squatch/registry.py` owns the decision registry: `Record` (`id` matching the stem regex, `kind` in `decision | tombstone`, `link` -- a ticket stem, a record id, or a box id, `reopen_after_days` an int of at least 1 with NO default, `message` the box id it resolves, and `body` the rationale and evidence as markdown), `load(repo)` parsing every `tickets/decisions/*.md` (YAML frontmatter via `safe_load`, refused fail-closed on a missing field, an unknown key, or an unparseable file -- never skipped), `write(repo, record, *, fs)` rendering the file, and `commit(repo, record, *, git)` adding and committing exactly `tickets/decisions/<id>.md` by pathspec through `squatch/git.py` with subject `squatch(decisions): <id>` -- the ticket-plane lane's discipline for the one directory the stem regex already reserves. Its first writer is triage (a later seed); this ticket lands the model, reader, writer, and their tests. `squatch/harvest.py`'s writer (read it in the worktree: it lands with `spine-harvest` and did not exist when this seed was authored) gains the producer hook: after the allowlist extraction and before returning, it files the harvested `run.md`'s second problems through `enqueue_second_problems` and records the ids in `Harvest.filed` (additive), the box built by `squatch/runner.py`'s terminal handler over the state dir and the seams it already holds; an enqueue failure is a harvest error under the existing soft contract (journaled, dispatch proceeds), and the setup-death short-circuit files nothing. `squatch/status.py` gains one `box` category: pending count, then each pending message's id, class, and summary cut to 80 characters. In this ticket's own diff, `bootstrap/suggestions.md` (read it in the worktree: it carries the engine's data-block delimiter and so cannot be a `Context` file) is ingested once with the module entry from the worktree (it resolves to the instance state dir) and then deleted with `git rm`; the deletion is the criteria-forced write the fence names. Tests for every rule above; `tests/test_drain.py` gains the era pin: a pending box message survives a whole drain untouched and no drain path reads or resolves it.

## Scope out
No consumer: no `squatch triage`, no `specs/triage.md`, no semantic dedup, no policy read, no ticket authored from a message (the triage seed). No storm-control circuit breaker (Phase 3, with the daemon's continuous producers), no tombstone auto-reopen or retro itemization (Phase 5, with the retro stage), no host `bug_report` intake or report inbox (Phase 6). No new CLI verb in `squatch/__main__.py` (section 18's verb list is closed; the ingestion is a module entry under `squatch/box.py`). No lock, no journal event, and no `effect_intent` for an enqueue: the box's durability is its atomic file, and the journal is the run record's, not the mailbox's. No enqueue on an `ok` run's record: section 12 names harvest, which runs on non-ok terminals only (section 11.2), as the producer; the merged-run gap is filed, not folded in. No change to the harvest allowlist beyond the additive `filed` field, to `ticket.md`, to the drain's eligibility or re-offer rules, to any frontmatter field, config key, or journal event type. No rewrite of a run record: the ids live in `harvest.json` and the box, never edited into `run.md`.

## Scope fence
- squatch/box.py
- squatch/registry.py
- squatch/harvest.py
- squatch/runner.py
- squatch/status.py
- bootstrap/suggestions.md
- tests/test_box.py
- tests/test_registry.py
- tests/test_harvest.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_cli.py

## Acceptance criteria
- In `tests/test_box.py`, `MESSAGE_CLASSES` equals exactly the five section 12 classes and `STATUSES` exactly `pending`, `authored`, `tombstoned`, `decided`; `Message` refuses a class or status outside them and refuses an unknown field.
- In `tests/test_box.py`, `signature` is identical for two reasons differing only in a path token, a digit run, or whitespace runs, and differs across classes, origins, stages, and outcomes.
- In `tests/test_box.py`, the first enqueue writes `<state_dir>/box/000001-<sig8>.json` with id `box-000001-<sig8>` and `reports` 1; a second enqueue with the same signature writes no second file, returns the same id with `duplicate` true, and leaves the record with `reports` 2; a third enqueue with a new signature is seq 2; `pending()` lists them in seq order; `resolve` of a pending message to `tombstoned` with a link atomically replaces the file, and `resolve` of a non-pending message or to a status outside the vocabulary is refused.
- In `tests/test_box.py`, `enqueue_second_problems` over a run record with two problem bullets and one `box-` citation under `## Second problems filed` files exactly two `suggestion` messages with `origin` the stem and returns their ids; a record with an empty section files nothing.
- In `tests/test_box.py`, `ingest` over a fixture of five non-empty lines (two of them list-marked, one blank line between) files five `suggestion` messages with `origin` `bootstrap-ingest` and marker-stripped summaries, and a second `ingest` of the same fixture files nothing and reports five duplicates.
- In `tests/test_box.py`, the module entry `uv run python -m squatch.box ingest <file>` run with a git worktree as cwd writes into the PARENT checkout's `<state_dir>/box/`, not the worktree's, exits 0, and exits 2 with a paved road on a missing file.
- In `tests/test_registry.py`, `Record` refuses a missing `reopen_after_days`, a `kind` outside `decision | tombstone`, and an id outside the stem regex; `write` then `load` round-trips a record; `load` over a directory holding one unparseable file is refused naming that file; `commit` puts exactly `tickets/decisions/<id>.md` on main in one commit whose subject is `squatch(decisions): <id>`.
- In `tests/test_harvest.py`, a non-ok run whose worktree `run.md` lists two second problems leaves `harvest.json` with `filed` naming two box ids that exist under `<state_dir>/box/` as pending `suggestion` messages with `origin` the stem, and a run record with none leaves `filed` empty.
- In `tests/test_terminal.py`, the terminal order harvest -> draws -> diagnosis -> terminal -> wipe is unchanged with the enqueue inside the harvest step, and a harvest whose enqueue raises still journals the terminal with `harvest_error` set and still wipes the worktree.
- In `tests/test_drain.py`, with one pending message under `<state_dir>/box/` a drain over two tickets runs to quiescence, exits 0, leaves that file byte-identical and still `pending`, journals no event naming the box, and prints no line naming the message.
- In `tests/test_cli.py`, `squatch status` with two pending messages prints a `box` section with the count and both ids.
- `git diff --name-only main...suggestion-box` lists `bootstrap/suggestions.md`, and `git ls-files bootstrap/suggestions.md` prints nothing on the branch.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_box.py tests/test_registry.py -q
uv run pytest tests/test_harvest.py tests/test_terminal.py tests/test_drain.py tests/test_cli.py -q
uv run python -m squatch.box --help
git diff --name-only main...suggestion-box
git ls-files bootstrap/suggestions.md
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if `squatch/harvest.py` as landed cannot carry an additive `filed` field without changing the terminal body's `harvest` shape, if the module entry cannot resolve the parent checkout through `squatch/git.py` without a new git verb beyond `rev-parse`, if the ingestion into the instance state dir cannot be performed from the implement worktree, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
