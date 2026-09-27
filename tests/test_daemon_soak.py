import json

import pytest
from pydantic import ValidationError

from eval.daemon_soak import dumps, write_report
from squatch.artifacts import (DAEMON_SOAK_MEMBERS, DAEMON_SOAK_REPORT, DaemonSoakEntry,
                               DaemonSoakReport)
from squatch.seams import LocalFilesystem
from squatch.stages import KNOWN_ARTIFACTS
from test_stages import (Agent, Harness, WIDGET, answer, env, git, implementer,  # noqa: F401
                         repo, review)


def entry(member, **changes):
    values = {
        "member": member,
        "fault": f"planted {member}",
        "observable": "the discriminating terminal or event",
        "expected": "passed",
        "observed": "passed",
        "disposition": "box",
        "producing_run": "soak/0",
        "auditor": "green",
        "green": True,
    }
    values.update(changes)
    return DaemonSoakEntry(**values)


def report(**changes):
    values = {
        "schema_version": 1,
        "produced_at_sha": "a" * 40,
        "injected_hours": 24,
        "entries": tuple(entry(member) for member in DAEMON_SOAK_MEMBERS),
    }
    values.update(changes)
    return DaemonSoakReport(**values)


def test_schema_is_closed_complete_and_derives_green():
    with pytest.raises(ValidationError):
        entry(DAEMON_SOAK_MEMBERS[0], observed="failed", green=True)
    with pytest.raises(ValidationError):
        entry(DAEMON_SOAK_MEMBERS[0], surprise=True)
    with pytest.raises(ValidationError):
        report(injected_hours=23.999)
    with pytest.raises(ValidationError):
        report(entries=tuple(entry(member) for member in DAEMON_SOAK_MEMBERS[:-1]))
    with pytest.raises(ValidationError):
        DaemonSoakReport(**report().model_dump(), surprise=True)


def test_report_dump_is_canonical_and_registered_for_ordinary_lane_validation():
    made = report()
    assert dumps(made) == json.dumps(made.model_dump(mode="json"),
                                     sort_keys=True, indent=2) + "\n"
    assert KNOWN_ARTIFACTS[DAEMON_SOAK_REPORT](dumps(made)) == made


async def test_writer_uses_uncommitted_outbox_and_stage_terminal_lifts_it(repo, env):
    made = report()

    def produce(request):
        implementer(env, WIDGET)(request)
        path = write_report(workspace=request.worktree, stem=request.ticket,
                            report=made, fs=LocalFilesystem())
        assert path == request.worktree / "tickets/widget-module" / DAEMON_SOAK_REPORT
        assert not (repo / "tickets/widget-module" / DAEMON_SOAK_REPORT).exists()

    agent = Agent(answer("implemented"), review("approve"), actions=[produce])
    delivery = await Harness(repo, env, agent).run()

    assert delivery.outcome == "ok"
    lifted = repo / "tickets/widget-module" / DAEMON_SOAK_REPORT
    assert lifted.read_text() == dumps(made)
    branch_files = git(repo, env, "ls-tree", "-r", "--name-only", "widget-module").splitlines()
    assert f"tickets/widget-module/{DAEMON_SOAK_REPORT}" not in branch_files


async def test_ordinary_lane_refuses_an_invalid_soak_report_before_writing(repo, env):
    def produce(request):
        implementer(env, WIDGET)(request)
        LocalFilesystem().write(
            request.worktree / "tickets/widget-module" / DAEMON_SOAK_REPORT, b"{}\n")

    delivery = await Harness(
        repo, env, Agent(answer("implemented"), actions=[produce])).run()

    assert delivery.outcome == "invalid_artifact"
    [finding] = delivery.findings
    assert finding.code == "invalid_artifact" and finding.path.endswith(DAEMON_SOAK_REPORT)
    assert not (repo / "tickets/widget-module" / DAEMON_SOAK_REPORT).exists()
