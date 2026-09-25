"""Shakeout member for a conflicted merge-admission rebase."""

import json
import sys
import textwrap
from pathlib import Path

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.harvest import Harvest
from squatch.llm import FakeLLM
from squatch.stages import RUN_RECORD_SECTIONS

GROUP = "shakeout-merge"


def _answer(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": "merge shakeout response"})


def _review() -> str:
    return json.dumps({"verdict": "approve", "summary": "merge shakeout approved",
                       "findings": []})


def _diagnosis() -> str:
    return json.dumps({"verdict": "retry", "lessons": ["rebase onto moved main"],
                       "reason": "the planted rebase conflict was refused"})


def _record() -> str:
    bodies = {"Outcome": "ok", "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str) -> str:
    command = (f'{sys.executable} -c "import pathlib,sys;'
               "sys.exit(not pathlib.Path('fixture/context.txt').is_file())\"")
    return textwrap.dedent(f"""\
        ---
        state: confirmed
        source: human
        priority: P1
        kind: chore
        ---
        ## Depends on
        - none

        ## Context
        - fixture/context.txt

        ## Goal
        Exercise the conflicted merge rebase for {stem}.

        ## Why
        A refused admission must abort before returning the branch for a later run.

        ## Scope in
        One conflicting edit to the fixture context.

        ## Scope out
        Engine code.

        ## Scope fence
        - fixture/context.txt

        ## Acceptance criteria
        - A conflicting edit to `fixture/context.txt` terminals gate_failed with the branch restored.

        ## Verification
        ```
        {command}
        ```

        ## Definition of rejected
        Stop if the fixture cannot advance main beneath a live worktree.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)


class _ActingFake(FakeLLM):
    def __init__(self, *script, actions=()):
        super().__init__(*script)
        self.actions = list(actions)

    async def call(self, request):
        action = self.actions.pop(0) if self.actions else None
        if action is not None:
            await action(request)
        return await super().call(request)


def _plant_conflict(bench: Bench, stem: str):
    async def action(request):
        worktree_file = request.worktree / "fixture" / "context.txt"
        worktree_file.write_text("branch conflict\n")
        record = request.worktree / "tickets" / stem / "run.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(_record())
        await bench.git.add(request.worktree, ("fixture/context.txt",))
        await bench.git.commit(request.worktree, "plant branch side of rebase conflict",
                               ("fixture/context.txt",))

        main_file = bench.repo / "fixture" / "context.txt"
        main_file.write_text("main conflict\n")
        await bench.git.add(bench.repo, ("fixture/context.txt",))
        await bench.git.commit(bench.repo, "advance main beneath live worktree",
                               ("fixture/context.txt",))
    return action


def _rebase_state(worktree: Path) -> tuple[bool, bool]:
    marker = worktree / ".git"
    line = marker.read_text().strip()
    admin = Path(line.removeprefix("gitdir: "))
    return (admin.joinpath("rebase-merge").exists(),
            admin.joinpath("rebase-apply").exists())


def _run_conflicted_rebase_aborted(bench: Bench) -> str:
    stem = "conflicted-rebase-aborted"
    fake = _ActingFake(
        _answer("implemented"), _review(), _diagnosis(),
        actions=(_plant_conflict(bench, stem), None, None))
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=fake)

    observed = {}
    production_factory = bench.runner._pipeline

    def observing_factory(journal):
        pipeline = production_factory(journal)
        admit = pipeline.merge.admit

        async def observe(ticket, delivery, *, run_seq):
            worktree = delivery.worktree
            observed["tree_before"] = await bench.git.rev_parse(bench.repo, "main^{tree}")
            admission = await admit(ticket, delivery, run_seq=run_seq)
            observed["tree_after"] = await bench.git.rev_parse(bench.repo, "main^{tree}")
            observed["worktree_head"] = await bench.git.rev_parse(worktree, "HEAD")
            observed["branch_head"] = await bench.git.rev_parse(
                bench.repo, f"refs/heads/{stem}")
            observed["rebase_state"] = _rebase_state(worktree)
            observed["admission"] = admission
            return admission

        pipeline.merge.admit = observe
        return pipeline

    bench.runner._pipeline = observing_factory
    try:
        bench.run(stem)
    finally:
        bench.runner._pipeline = production_factory

    harvest_path = bench.repo / "tickets" / stem / "attempts" / "0" / "harvest.json"
    harvest = Harvest.model_validate_json(harvest_path.read_bytes())
    admission = observed.get("admission")
    admission_findings = getattr(admission, "findings", ())
    finding = admission_findings[0] if len(admission_findings) == 1 else None
    harvested = harvest.findings[0] if len(harvest.findings) == 1 else None
    road = finding is not None and "re-run the stem" in finding.paved_road
    if (bench.terminal(stem, 0) == "gate_failed"
            and finding is not None and finding.code == "post_rebase_regate" and road
            and harvested == finding and harvest.stage == "merge"
            and observed.get("rebase_state") == (False, False)
            and observed.get("worktree_head") == observed.get("branch_head")
            and observed.get("tree_before") == observed.get("tree_after")):
        return "gate_failed:rebase_aborted"
    return (f"terminal={bench.terminal(stem, 0)};finding="
            f"{getattr(finding, 'code', None)};road={road};"
            f"rebase_state={observed.get('rebase_state')};"
            f"head_restored={observed.get('worktree_head') == observed.get('branch_head')};"
            f"main_unchanged={observed.get('tree_before') == observed.get('tree_after')};"
            f"harvested={harvested == finding}")


MEMBERS = (
    Member(
        "conflicted_rebase_aborted",
        "main and the live ticket branch commit conflicting edits to the same fixture lines",
        ("gate_failed carries post_rebase_regate with the re-run road; before cleanup the "
         "worktree has neither rebase state directory, HEAD equals the branch head, and "
         "main's tree is unchanged"),
        "gate_failed:rebase_aborted",
        "tickets/<stem>/attempts/<n>/harvest.json",
        _run_conflicted_rebase_aborted,
    ),
)
