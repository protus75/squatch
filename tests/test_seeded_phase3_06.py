"""Merge/rework activation seeds and the next finite Phase 3 admission."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
PHASE3_06 = {
    "merge-queue-activation": ("phase3-continue-06",),
    "rework-activation": ("merge-queue-activation",),
    "phase3-continue-07": ("merge-queue-activation", "rework-activation"),
}
FENCES = {
    "merge-queue-activation": (
        "squatch/merge.py", "tests/test_mergequeue.py",
        "tests/test_daemon_composition.py",
    ),
    "rework-activation": (
        "squatch/daemon.py", "squatch/rework.py", "squatch/mergequeue.py",
        "tests/test_rework.py", "tests/test_daemon_composition.py",
    ),
    "phase3-continue-07": ("tickets", "tests/test_seeded_phase3_07.py"),
}
OWNERSHIP = {
    "merge-queue-activation": {
        "owns": [],
        "hooks": ["squatch/merge.py", "tests/test_mergequeue.py",
                  "tests/test_daemon_composition.py"],
    },
    "rework-activation": {
        "owns": [],
        "hooks": ["squatch/daemon.py", "squatch/rework.py", "squatch/mergequeue.py",
                  "tests/test_rework.py", "tests/test_daemon_composition.py"],
    },
    "phase3-continue-07": {
        "owns": ["tickets", "tests/test_seeded_phase3_07.py"], "hooks": [],
    },
}
CONTEXT = {
    "merge-queue-activation": (
        "squatch/merge.py", "tests/test_mergequeue.py",
        "tests/test_daemon_composition.py", "squatch/__main__.py", "squatch/runner.py",
    ),
    "rework-activation": (
        "squatch/daemon.py", "squatch/rework.py", "squatch/mergequeue.py",
        "tests/test_rework.py", "tests/test_daemon_composition.py", "squatch/merge.py",
    ),
    "phase3-continue-07": (
        "tests/test_seeded_phase3_04.py", "squatch/config.py", "squatch/daemon.py",
        "squatch/mergequeue.py", "tests/test_daemon_composition.py",
        "tests/test_mergequeue.py",
    ),
}

# Verified against 6c75000a0767ef70e27884db0df5a3824a22cae8, including absence
# of the data-block delimiter in every listed blob. Sizes are render inputs only;
# later changes to these paths are not invariants of the seed proof.
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_04.py": 11063,
    "squatch/config.py": 10260,
    "squatch/daemon.py": 2946,
    "squatch/mergequeue.py": 12798,
    "tests/test_daemon_composition.py": 2671,
    "tests/test_mergequeue.py": 24597,
    "squatch/merge.py": 20407,
    "squatch/__main__.py": 10674,
    "squatch/runner.py": 23428,
    "squatch/rework.py": 8417,
    "tests/test_rework.py": 10353,
}
NEW_AT_AUTHORING = {"tests/test_seeded_phase3_07.py"}
FORBIDDEN_CONTEXT = {"squatch/specs.py", "specs/implement.md", "specs/rework.md"}
SUFFIX = (
    ("merge-queue-activation", "rework-activation"),
    ("background-consumers", "control-inbox"),
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"),
    ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",),
    ("heartbeat",),
    ("restart-timers",),
    ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",),
    ("checkpoint-push",),
    ("daemon-soak",),
    ("soak-run",),
    ("phase3-exit",),
)
SUCCESSOR_CONTEXT = {
    "background-consumers": [
        "squatch/daemon.py", "squatch/mergequeue.py", "tests/test_daemon_composition.py",
    ],
    "control-inbox": ["squatch/daemon.py", "tests/test_daemon_composition.py"],
    "phase3-continue-08": [
        "tests/test_seeded_phase3_04.py", "squatch/config.py", "squatch/daemon.py",
        "squatch/mergequeue.py", "tests/test_daemon_composition.py",
        "tests/test_mergequeue.py",
    ],
}
SUCCESSOR_OWNERSHIP = {
    "background-consumers": {
        "owns": ["tests/test_daemon_tasks.py"],
        "hooks": ["squatch/daemon.py"],
    },
    "control-inbox": {
        "owns": ["squatch/control.py", "tests/test_control.py"],
        "hooks": ["squatch/daemon.py", "tests/test_daemon_tasks.py"],
    },
    "phase3-continue-08": {
        "owns": ["tickets", "tests/test_seeded_phase3_08.py"], "hooks": [],
    },
}
SUCCESSOR_NEW = {
    "squatch/control.py", "tests/test_daemon_tasks.py", "tests/test_control.py",
    "tests/test_seeded_phase3_08.py",
}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO,
        plan=(REPO / PLAN_FILE).read_text(),
        resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _yaml_blocks(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def test_emitted_batch_is_exact_linted_and_capped():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(PHASE3_06) == (
        "merge-queue-activation", "rework-activation", "phase3-continue-07")
    assert set(re.findall(r"`tickets/([^/]+)/ticket\.md`",
                          _section("phase3-continue-06", "Scope in"))) == set(PHASE3_06)
    assert len(PHASE3_06) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_06.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state) == ("seed", "confirmed"), stem
        assert ticket.plan_sections == ("20",), stem
        assert ticket.depends == depends, stem
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium"), stem
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150), stem
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes <= config.drain.max_ticket_minutes


def test_fences_context_closure_and_keyed_ownership_are_exact():
    for stem in PHASE3_06:
        ticket = _ticket(stem)
        assert ticket.scope_fence == FENCES[stem], stem
        assert ticket.context == CONTEXT[stem], stem
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING), stem
        assert set(ticket.context).isdisjoint(FORBIDDEN_CONTEXT), stem
        if stem == "phase3-continue-07":
            ownership = _yaml_blocks("phase3-continue-06")[0]
            assert ownership["ownership"][stem] == OWNERSHIP[stem]
        else:
            ownership = next(block for block in _yaml_blocks(stem) if "ownership" in block)
            assert ownership == {"ownership": {stem: OWNERSHIP[stem]}}, stem
        assert set(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"]) == set(FENCES[stem])
        for path in FENCES[stem]:
            if path == "tickets":
                continue
            assert path in EXISTING_AT_AUTHORING or path in NEW_AT_AUTHORING
            if path in EXISTING_AT_AUTHORING:
                assert path in ticket.context
    assert set(EXISTING_AT_AUTHORING).isdisjoint(NEW_AT_AUTHORING)
    assert NEW_AT_AUTHORING == {"tests/test_seeded_phase3_07.py"}


def test_merge_activation_closes_predecessors_and_pins_concrete_adapters():
    scope = _section("merge-queue-activation", "Scope in")
    criteria = _section("merge-queue-activation", "Acceptance criteria")
    scope_out = _section("merge-queue-activation", "Scope out")
    for phrase in (
        "builds `Pipeline.merge_queue` by calling the existing `compose_merge_queue`",
        "loads the `Ticket` by the candidate stem",
        "`Git.rev_parse` of main and the candidate worktree's `HEAD`",
        "retains its `Invoice` by `(stem, run_seq)`",
        "runs that loaded ticket's `## Verification` commands through the existing `Verification` gate",
        "same on-disk `tickets/<stem>/review.md` approval check (`Merge._approval` via `load_review`)",
        '`Git.rev_parse(candidate.worktree, "HEAD")`',
        "`Merge._approval(stem, pre_rebase_head)`",
        "No journal approval lookup",
        "overrides public `admit`",
        "`super().admit(candidate)`",
        "Only the candidate's own admission moves its worktree",
        "Clear the capture and adapter Invoice in a `finally` block",
        "Do not override private MergeQueue methods",
        "`compose_merge_queue` constructs that subtype for all callers",
        "Do not rely on ORIG_HEAD",
        "isinstance(pipeline.merge_queue, MergeQueue)",
    ):
        assert phrase in scope
    assert "`Merge.admit` and `Pipeline.run` remain unchanged" in scope_out
    assert "`not hasattr(pipeline, \"merge_queue\")`" in scope
    assert "`test_additive_composition_hook_does_not_change_phase1_composition`" in scope
    assert "`test_mergequeue_has_no_scheduler_or_watcher_dependency`" in scope
    assert "A fresh approve pinned to the pre-rebase head integrates after HEAD changes" in criteria
    assert "a stale or missing pin is refused without squash" in criteria
    assert "An up-to-date rebase also succeeds with a fresh pin" in criteria
    assert "even when ORIG_HEAD is absent or stale" in criteria
    assert "cleared on success, refusal and exception" in criteria
    assert "real in-process `__main__` factory/Runner composition" in criteria
    for path in ("squatch/daemon.py", "squatch/mergequeue.py", "squatch/git.py"):
        assert path in scope_out and path not in FENCES["merge-queue-activation"]
    assert CONTEXT["merge-queue-activation"] == (
        *FENCES["merge-queue-activation"], "squatch/__main__.py", "squatch/runner.py")


def test_merge_activation_quotes_base_interfaces_and_names_the_right_proof_sites():
    scope = _section("merge-queue-activation", "Scope in")
    # Pinned signatures survive later activation edits; live introspection would
    # make the authoring proof constrain the implementation it commissions.
    for signature in (
        "    def __init__(self, *, repo: Path, config: Config, git: Git, process: ProcessExec,\n"
        "                 fs: Filesystem, journal: Journal, env: Mapping[str, str],\n"
        "                 regate: Check, integration_check: Check, integrate: Integrate,\n"
        "                 timeout: float = 60.0):",
        "    async def admit(self, candidate: Candidate) -> Admission:",
        "def compose_merge_queue(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,\n"
        "                        process: ProcessExec, fs: Filesystem, git: Git,\n"
        "                        regate, integration_check, integrate):",
        "def compose_pipeline(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,\n"
        "                     clock: Clock, process: ProcessExec, fs: Filesystem, git: Git) -> Pipeline:",
        "    def _approval(self, stem: str, head: str) -> list[Finding]:",
        "    async def _regate(self, ticket: Ticket, candidate: PackingSlip, worktree: Path,\n"
        "                      run_seq: int) -> Invoice:",
        "    async def _squash(self, ticket: Ticket, invoice: Invoice, reviewed: str, run_seq: int) -> dict:",
    ):
        assert signature in scope
    assert "env=child_env(env, {p.auth for p in config.providers if p.auth})" in scope
    assert "timeout=config.drain.max_ticket_minutes * 60" in scope
    criteria = _section("merge-queue-activation", "Acceptance criteria").splitlines()
    for name in ("test_additive_composition_hook_does_not_change_phase1_composition",
                 "test_mergequeue_has_no_scheduler_or_watcher_dependency"):
        proof = [line for line in criteria if name in line]
        assert len(proof) == 1
        assert proof[0].startswith("- `tests/test_mergequeue.py`")
    [composition] = [line for line in criteria
                     if line.startswith("- `tests/test_daemon_composition.py`")]
    assert "isinstance(pipeline.merge_queue, MergeQueue)" in composition
    assert "dispatch/config and no-serve" in composition
    assert "not hasattr" not in composition
    assert "remain unchanged" not in "\n".join(criteria)


def test_rework_activation_repairs_constructor_sources_and_reachability_contract():
    scope = _section("rework-activation", "Scope in")
    criteria = _section("rework-activation", "Acceptance criteria")
    scope_out = _section("rework-activation", "Scope out")
    for phrase in (
        "`compose_daemon_rework`",
        "one named composition function in `squatch/daemon.py`",
        "`queue=pipeline.merge_queue`",
        "Its explicit inputs are `repo`",
        "the production `Driver`",
        "the lock-held `Journal`",
        "the injected `Filesystem`",
        "already loaded `specs/rework.md` `Spec`",
        "defaulting to the registry values `medium` and `medium`",
        "reachable from the production-root import closure",
        "invocation from `_locked` is deferred to the later `background-consumers` boundary",
        "only after its serial slot unlocks",
        "`test_rework_remains_unreachable_from_the_production_root`",
        "`test_spec_is_one_composite_rework_order_surface`",
    ):
        assert phrase in scope
    assert "no `__main__._locked` or Runner call site is added" in criteria
    assert "Do not add a call from `squatch.__main__._locked`" in scope
    assert "Do not edit `squatch/merge.py`, `squatch/__main__.py`, `squatch/runner.py`" in scope_out
    assert "specs/rework.md" not in CONTEXT["rework-activation"]
    assert "squatch/merge.py" in CONTEXT["rework-activation"]
    for stem in ("merge-queue-activation", "rework-activation"):
        assert "tests/test_daemon_composition.py" in CONTEXT[stem]
        assert "tests/test_daemon_composition.py" in _section(stem, "Verification")
    for phrase in ("update/split/escalate", "supersedes", "approval invalidation",
                   "validated writes", "consumption after slot unwind"):
        assert phrase in scope


def test_successor_pins_context_ownership_and_predecessor_test_closure():
    blocks = _yaml_blocks("phase3-continue-07")
    assert blocks[0] == {"context": SUCCESSOR_CONTEXT}
    assert blocks[1] == {"ownership": SUCCESSOR_OWNERSHIP}
    for stem, record in SUCCESSOR_OWNERSHIP.items():
        fence = set(record["owns"] + record["hooks"])
        assert fence
        assert set(record["owns"]).isdisjoint(record["hooks"])
        assert set(SUCCESSOR_CONTEXT[stem]) <= set(EXISTING_AT_AUTHORING)
        assert set(SUCCESSOR_CONTEXT[stem]).isdisjoint(SUCCESSOR_NEW | FORBIDDEN_CONTEXT)
        assert (fence & set(EXISTING_AT_AUTHORING)) <= set(SUCCESSOR_CONTEXT[stem])
        if stem != "phase3-continue-08":
            assert "tests/test_daemon_composition.py" in SUCCESSOR_CONTEXT[stem]
    owners = {path: stem for stem, record in SUCCESSOR_OWNERSHIP.items()
              for path in record["owns"] if path != "tickets"}
    assert owners == {
        "tests/test_daemon_tasks.py": "background-consumers",
        "squatch/control.py": "control-inbox",
        "tests/test_control.py": "control-inbox",
        "tests/test_seeded_phase3_08.py": "phase3-continue-08",
    }
    assert set(owners) == SUCCESSOR_NEW
    control = _path("phase3-continue-07").read_text()
    assert "`tests/test_daemon_tasks.py` as a hook and runs it in Verification" in control
    assert "Both deliverable seeds preserve `tests/test_daemon_composition.py` unchanged and run it in Verification" in control
    assert "tests/test_daemon_tasks.py" not in SUCCESSOR_CONTEXT["control-inbox"]
    assert "tests/test_daemon_tasks.py" in SUCCESSOR_OWNERSHIP["control-inbox"]["hooks"]
    assert "tests/test_mergequeue.py" in SUCCESSOR_CONTEXT["phase3-continue-08"]
    assert set(SUCCESSOR_CONTEXT["phase3-continue-08"]).isdisjoint(SUCCESSOR_NEW)
    new_line = next(line for line in _section("phase3-continue-07", "Scope in").splitlines()
                    if "are new at authoring" in line)
    assert all(f"`{path}`" in new_line for path in SUCCESSOR_NEW)
    assert set(re.findall(r"`([^`]+)`", new_line)) == SUCCESSOR_NEW | {"NEW_AT_AUTHORING"}
    criteria = _section("phase3-continue-07", "Acceptance criteria")
    for phrase in ("EXISTING_AT_AUTHORING sizes", "exact four-path NEW_AT_AUTHORING set",
                   "every existing fence entry is Context", "max-effort synthetic renders",
                   "tests/test_mergequeue.py", "authoring-time size", "successor == full[1:]"):
        assert phrase in criteria
    assert "background-consumers as tests/test_daemon_tasks.py's owner" in criteria
    assert "control-inbox as squatch/control.py and tests/test_control.py's owner" in criteria
    assert "Typed-inbox construction belongs only to control-inbox" in _section(
        "phase3-continue-07", "Scope out")


def test_continuation_carries_two_exact_shrinking_suffixes():
    parent = _yaml_blocks("phase3-continue-06")
    assert tuple(tuple(group) for group in parent[1]) == SUFFIX
    assert tuple(tuple(group) for group in parent[2]) == SUFFIX[1:]
    successor = _yaml_blocks("phase3-continue-07")
    assert tuple(tuple(group) for group in successor[2]) == SUFFIX[1:]
    assert tuple(tuple(group) for group in successor[3]) == SUFFIX[2:]
    assert "merge-queue-activation" not in {stem for group in successor[2] for stem in group}
    assert "rework-activation" not in {stem for group in successor[2] for stem in group}


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_06:
        ticket = _ticket(stem)
        workspace = (f"stem: {stem}\nbranch: {stem}\n"
                     f"run record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n")
        context = "".join(
            f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
