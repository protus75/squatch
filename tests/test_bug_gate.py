"""The bug regression gate proves the defect exists before the branch fix."""

import shutil
from pathlib import Path

import pytest

from squatch.redact import Redactor
from squatch.seams import LocalFilesystem
from squatch.stages import BugEvidence, PackingSlip
from squatch.tickets import Regression, Ticket, TicketLintError, lint_ticket


class ReplayGit:
    def __init__(self, base: Path, changed: tuple[str, ...]):
        self.base = base
        self.changed = changed
        self.removed = []
        self.listed = []

    async def diff_names(self, repo, base, branch):
        return list(self.changed)

    async def ls_files(self, workspace):
        self.listed.append(workspace)
        return sorted(str(path.relative_to(workspace)) for path in workspace.rglob("*")
                      if path.is_file())

    async def worktree_add_detached(self, repo, path, commit):
        shutil.copytree(self.base, path)

    async def worktree_remove(self, repo, path):
        self.removed.append(path)
        shutil.rmtree(path)


class RegressionProcess:
    async def run(self, argv, *, cwd, env, timeout):
        # The branch is green only with its fix; the base is red only with the
        # branch's carried test content overlaid.
        app = (cwd / "app.py").read_text()
        test = (cwd / "tests" / "test_app.py").read_text()
        return (0 if app == "fixed" or test == "old test" else 1, "", "")


def bug_ticket(*, carries=("tests/test_app.py",)):
    return Ticket(
        stem="bug-fix", state="confirmed", source="seed", priority="P1", kind="bug",
        agent_tier="medium", agent_effort="medium", gate_bypass=(), depends=(), context=(),
        plan_sections=(), goal="fix", scope_fence=("app.py", "tests/test_app.py"),
        verification=(), regression=Regression(("fixture-regression",), carries),
        expected_minutes=1, stuck_minutes=1, exit_read_window=())


def slip():
    return PackingSlip(stem="bug-fix", verdict="implemented", summary="fix", branch="bug-fix",
                       base="base", head="head", produced_by_spec_version="test",
                       produced_at_sha="head")


def setup_replay(tmp_path, *, base_app="broken", branch_app="fixed", base_test=True,
                 branch_extra=None):
    base = tmp_path / "base"
    branch = tmp_path / "branch"
    for root, app in ((base, base_app), (branch, branch_app)):
        (root / "tests").mkdir(parents=True)
        (root / "app.py").write_text(app)
    if base_test:
        (base / "tests" / "test_app.py").write_text("old test")
    (branch / "tests" / "test_app.py").write_text("new test")
    if branch_extra is not None:
        path = branch / branch_extra
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("branch input")
    return base, branch


def test_bug_ticket_grammar_requires_kind_and_regression_section(tmp_path):
    (tmp_path / "app.py").write_text("")
    ticket = """---
priority: P1
kind: bug
---
## Depends on
- none

## Context
- app.py

## Goal
fix

## Why
regression

## Scope in
app

## Scope out
none

## Scope fence
- app.py

## Acceptance criteria
- `app.py` changes.

## Verification
```
fixture-regression
```

## Definition of rejected
bad evidence

## Time budget
- expected: 1m
- stuck: 1m
"""
    with pytest.raises(TicketLintError, match="Regression"):
        lint_ticket(ticket, stem="bug-fix", repo=tmp_path, plan=None, resolve_stem=lambda _: False)
    valid = ticket + """
## Regression
```
fixture-regression
```
- carries: tests/test_app.py
"""
    parsed = lint_ticket(valid, stem="bug-fix", repo=tmp_path, plan=None,
                         resolve_stem=lambda _: False)
    assert parsed.kind == "bug" and parsed.regression is not None
    with pytest.raises(TicketLintError, match="kind: bug"):
        lint_ticket(valid.replace("kind: bug", "kind: feature"), stem="bug-fix", repo=tmp_path,
                    plan=None, resolve_stem=lambda _: False)


async def check(tmp_path, *, base_app="broken", branch_app="fixed", base_test=True,
                branch_extra=None, changed=("app.py", "tests/test_app.py"),
                carries=("tests/test_app.py",)):
    base, branch = setup_replay(
        tmp_path, base_app=base_app, branch_app=branch_app, base_test=base_test,
        branch_extra=branch_extra)
    git = ReplayGit(base, changed)
    gate = BugEvidence(git, tmp_path, RegressionProcess(), bug_ticket(carries=carries), {},
                       Redactor({}), LocalFilesystem(), base_worktree=tmp_path / "base-worktree")
    return await gate.check(slip(), branch)


async def test_bug_gate_accepts_branch_pass_and_base_failure_with_carried_overlay(tmp_path):
    report = await check(tmp_path)
    assert report.verdict == "pass"


async def test_bug_gate_rejects_a_test_missing_from_base_when_not_carried(tmp_path):
    report = await check(tmp_path, base_test=False, carries=("tests/other.py",))
    assert report.verdict == "fail"
    assert "not covered by `carries`" in report.findings[0].message


async def test_bug_gate_accepts_a_test_missing_from_base_only_when_carried(tmp_path):
    report = await check(tmp_path, base_test=False)
    assert report.verdict == "pass"


async def test_bug_gate_rejects_an_uncarried_branch_added_non_test_input(tmp_path):
    report = await check(
        tmp_path, branch_extra="data/case.json",
        changed=("app.py", "tests/test_app.py", "data/case.json"))
    assert report.verdict == "fail"
    assert "data/case.json" in report.findings[0].message


async def test_bug_gate_rejects_a_merge_base_that_passes_with_the_overlay(tmp_path):
    report = await check(tmp_path, base_app="fixed")
    assert report.verdict == "fail"
    assert "merge base with carries overlay" in report.findings[0].message


async def test_bug_gate_rejects_a_branch_head_that_fails(tmp_path):
    report = await check(tmp_path, branch_app="broken")
    assert report.verdict == "fail"
    assert "branch head" in report.findings[0].message


async def test_bug_gate_rejects_an_uncarried_regression_in_an_existing_test_file(tmp_path):
    report = await check(tmp_path, carries=("tests/other.py",))
    assert report.verdict == "fail"
    assert "tests/test_app.py" in report.findings[0].message
    assert "not covered by `carries`" in report.findings[0].message


@pytest.mark.parametrize("renamed", [False, True])
async def test_bug_gate_allows_deleted_test_paths_with_carried_regression(tmp_path, renamed):
    base, branch = setup_replay(tmp_path, base_test=not renamed)
    (base / "tests" / "test_old.py").write_text("old test")
    git = ReplayGit(base, ("app.py", "tests/test_old.py", "tests/test_app.py"))
    replay = tmp_path / "base-worktree"
    gate = BugEvidence(git, tmp_path, RegressionProcess(), bug_ticket(), {}, Redactor({}),
                       LocalFilesystem(), base_worktree=replay)

    report = await gate.check(slip(), branch)

    assert report.verdict == "pass"
    assert git.listed == [branch]
    assert git.removed == [replay]
    assert not replay.exists()
