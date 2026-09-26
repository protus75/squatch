---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-06

## Context
- squatch/merge.py
- tests/test_mergequeue.py
- tests/test_daemon_composition.py
- squatch/__main__.py
- squatch/runner.py

## Plan contract
- section 20

## Goal
Expose the existing serial merge queue with concrete adapters in the production pipeline.

## Why
The independently tested queue needs a production composition before background consumers can own its lifetime.

## Scope in
In `squatch/merge.py`, `compose_pipeline` builds `Pipeline.merge_queue` by calling the existing `compose_merge_queue`. Keep its child_env filtering and configured drain timeout. Extend Pipeline construction to expose that queue; there is one queue construction path for all production callers. Preserve the existing two-positional-argument `Pipeline(stages, merge)` constructor used by predecessor unit-test harnesses outside this fence: add `merge_queue=None` as the trailing compatibility default, while `compose_pipeline` always supplies the concrete queue. Those direct harness instances are not production composition and do not authorize a second queue construction path.

The regate adapter loads the `Ticket` by the candidate stem from the repository ticket plane using the existing ticket linter and dependency resolver. Build a post-rebase `PackingSlip` from `Git.rev_parse` of main and the candidate worktree's `HEAD`, with the candidate stem/branch, implemented verdict, ticket goal as summary, MERGE_VERSION and candidate HEAD provenance. Call `Merge._regate(ticket, slip, candidate.worktree, candidate.run_seq)` and return its hard findings. It retains its `Invoice` by `(stem, run_seq)` for integrate. The integration callback runs that loaded ticket's `## Verification` commands through the existing `Verification` gate on the rebased worktree, using the same slip, process, redactor and secret-filtered environment as merge verification; return the resulting gate findings. No new configured integration gate exists or is needed.

The integrate adapter uses the same on-disk `tickets/<stem>/review.md` approval check (`Merge._approval` via `load_review`). Retain the reviewed pre-rebase head by `(stem, run_seq)`: a merge.py-local MergeQueue subclass overrides public `admit`, captures `Git.rev_parse(candidate.worktree, "HEAD")`, then awaits `super().admit(candidate)`. Only the candidate's own admission moves its worktree, so capture before waiting for the serial slot is safe. Clear the capture and adapter Invoice in a `finally` block, including cancellation. `compose_merge_queue` constructs that subtype for all callers, preserving its existing callback interface. Do not override private MergeQueue methods. Do not rely on ORIG_HEAD, which can be absent or stale for an up-to-date rebase. Regate returns `Merge._approval(stem, pre_rebase_head)` findings before integration if approval is missing or stale; integrate checks that same approval path and obtains reviewed_sha from its approved review record before calling `Merge._squash(ticket, invoice, reviewed_sha, run_seq)`. No journal approval lookup or second approval implementation is introduced.

These existing signatures are copied from base 6c75000a0767ef70e27884db0df5a3824a22cae8 so their interfaces remain visible when Context excerpts are truncated. Read their full implementations before editing. The first two belong to MergeQueue, the next two are module functions in merge.py, and the final three belong to Merge:
```python
    def __init__(self, *, repo: Path, config: Config, git: Git, process: ProcessExec,
                 fs: Filesystem, journal: Journal, env: Mapping[str, str],
                 regate: Check, integration_check: Check, integrate: Integrate,
                 timeout: float = 60.0):
    async def admit(self, candidate: Candidate) -> Admission:
def compose_merge_queue(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
                        process: ProcessExec, fs: Filesystem, git: Git,
                        regate, integration_check, integrate):
def compose_pipeline(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
                     clock: Clock, process: ProcessExec, fs: Filesystem, git: Git) -> Pipeline:
    def _approval(self, stem: str, head: str) -> list[Finding]:
    async def _regate(self, ticket: Ticket, candidate: PackingSlip, worktree: Path,
                      run_seq: int) -> Invoice:
    async def _squash(self, ticket: Ticket, invoice: Invoice, reviewed: str, run_seq: int) -> dict:
```
Candidate carries only stem, branch, worktree and run_seq. Check callbacks asynchronously return a sequence of Finding; integrate asynchronously returns None. `Merge._approval` requires verdict == approve and reviewed_sha == the supplied head; `_squash` consumes Invoice.changed_files and writes the reviewed SHA trailer. `compose_merge_queue` currently forwards all three callbacks into MergeQueue with `env=child_env(env, {p.auth for p in config.providers if p.auth})` and `timeout=config.drain.max_ticket_minutes * 60`. Preserve those semantics while changing its constructed type. The public queue admission and ordering are exercised by `tests/test_mergequeue.py`.

In `tests/test_mergequeue.py`, migrate `test_additive_composition_hook_does_not_change_phase1_composition` from the literal `not hasattr(pipeline, "merge_queue")` to `isinstance(pipeline.merge_queue, MergeQueue)`. Preserve `test_mergequeue_has_no_scheduler_or_watcher_dependency` and the direct serial admission, regate/integration/tree-hash, conflict resolution and post-unwind handoff tests. Add concrete adapter tests there, including moved-main and up-to-date approval cases.

In `tests/test_daemon_composition.py`, drive the real in-process `__main__` factory/Runner composition and observe `isinstance(pipeline.merge_queue, MergeQueue)` on the resulting production pipeline. The factory in `_locked` calls compose_pipeline, and Runner.dispatch invokes that factory with its lock-held journal. Instrument those existing seams without substituting a fake pipeline factory. Preserve existing dispatch/config and no-serve contracts; no production main or Runner edit is required.

```yaml
ownership:
  merge-queue-activation:
    owns: []
    hooks:
      - squatch/merge.py
      - tests/test_mergequeue.py
      - tests/test_daemon_composition.py
```

## Scope out
`Merge.admit` and `Pipeline.run` remain unchanged. Preserve `squatch/daemon.py`, `squatch/mergequeue.py`, `squatch/git.py`, `squatch/__main__.py` and `squatch/runner.py` unchanged. Do not add background consumers, pause/hold policy, Rework activation, config keys or a CLI verb. Do not construct a second queue path.

## Scope fence
- squatch/merge.py
- tests/test_mergequeue.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_mergequeue.py` proves compose_pipeline exposes a MergeQueue built through compose_merge_queue with concrete regate, integration and integrate adapters, using the configured timeout and secret-filtered environment; the existing admission tests pass.
- `tests/test_mergequeue.py` proves the trailing `merge_queue=None` compatibility default preserves predecessor direct `Pipeline(stages, merge)` harness construction, while every `compose_pipeline` result has a concrete MergeQueue.
- `tests/test_mergequeue.py` proves regate loads the candidate's Ticket, derives the post-rebase slip from main and candidate HEAD, hands its Invoice to integrate by (stem, run_seq), and integration runs the ticket's Verification commands in the rebased worktree. A red check prevents squash; the approved SHA reaches the squash trailer.
- `tests/test_mergequeue.py` proves: A fresh approve pinned to the pre-rebase head integrates after HEAD changes; a stale or missing pin is refused without squash. An up-to-date rebase also succeeds with a fresh pin even when ORIG_HEAD is absent or stale. Captured head and Invoice are cleared on success, refusal and exception, including cancellation.
- `tests/test_mergequeue.py` migrates `test_additive_composition_hook_does_not_change_phase1_composition`'s literal `not hasattr(pipeline, "merge_queue")` to `isinstance(pipeline.merge_queue, MergeQueue)` and preserves `test_mergequeue_has_no_scheduler_or_watcher_dependency`.
- `tests/test_daemon_composition.py` drives the real in-process `__main__` factory/Runner composition and observes `isinstance(pipeline.merge_queue, MergeQueue)`, preserving its dispatch/config and no-serve contracts.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_mergequeue.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the real production factory cannot expose the queue within this fence, a predecessor assertion requires an unfenced edit beyond the explicitly preserved two-argument constructor compatibility, the existing verification gate cannot serve integration, or approval requires a second path.

## Time budget
- expected: 75m
- stuck: 150m
