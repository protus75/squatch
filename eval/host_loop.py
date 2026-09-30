"""Run the supervised fixture host loop without writing terminal artifacts."""

import asyncio
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

from squatch.artifacts import HostLoopEntry, HostLoopReport
from squatch.control import ControlRequest, publish_control, supervised_merge_holds
from squatch.git import Git
from squatch.journal import Event, read_events
from squatch.seams import (Filesystem, LocalFilesystem, ProcessExec, SubprocessExec,
                           kill_group)


FIXTURE = Path(__file__).resolve().parent.parent / "hosts" / "fixture"
ENGINE_ROOT = Path(__file__).resolve().parent.parent
INITIAL_SCENARIOS = ("deterministic-app", "machine-introduced-escape")
STEMS = {
    "deterministic-app": "fixture-deterministic-app",
    "report-to-regression": "fixture-regression-fix",
    "machine-introduced-escape": "fixture-machine-escape",
}


class HostLoopEvidenceError(RuntimeError):
    """The fixture did not leave the required production evidence."""


def _environment(host: Path, source: Mapping[str, str]) -> dict[str, str]:
    env = {key: value for key, value in source.items()
           if key not in {"ANTHROPIC_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"}}
    env.update({
        "PATH": str(host / "bin") + os.pathsep + source.get("PATH", ""),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch",
        "GIT_AUTHOR_EMAIL": "squatch@fixture.invalid",
        "GIT_COMMITTER_NAME": "squatch",
        "GIT_COMMITTER_EMAIL": "squatch@fixture.invalid",
    })
    return env


async def _wait_for(state: Path, predicate: Callable[[tuple[Event, ...]], object | None],
                    *, seconds: float = 90) -> tuple[object, tuple[Event, ...]]:
    deadline = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < deadline:
        events = tuple(read_events(state))
        if (value := predicate(events)) is not None:
            return value, events
        await asyncio.sleep(.02)
    raise HostLoopEvidenceError("fixture serve did not produce the expected journal evidence")


class FixtureHostLoop:
    """Copy the fixture, launch real ``serve``, and supervise its held merges."""

    def __init__(self, *, fixture: Path = FIXTURE, process: ProcessExec | None = None,
                 fs: Filesystem | None = None, env: Mapping[str, str] | None = None) -> None:
        self.fixture = Path(fixture)
        self.process = process or SubprocessExec()
        self.fs = fs or LocalFilesystem()
        self.env = dict(os.environ if env is None else env)

    async def run(self, *, evidence_root: Path | None = None) -> HostLoopReport:
        root = (Path(evidence_root) if evidence_root is not None
                else Path(tempfile.mkdtemp(prefix="squatch-host-loop-")))
        host = root / "fixture-host"
        shutil.copytree(self.fixture, host)
        shutil.copy2(ENGINE_ROOT / "SQUATCH_PLAN.md", host / "SQUATCH_PLAN.md")
        env = _environment(host, self.env)
        git = Git(self.process, env=env, timeout=30)

        await self._command([sys.executable, "-m", "squatch", "--config",
                             str(host / "config.yaml"), "core"], host, env)
        for scenario in INITIAL_SCENARIOS:
            authored = await self._fixture_author(host, env, scenario)
            destination = host / "tickets" / authored["stem"] / "ticket.md"
            self.fs.write(destination, authored["ticket"].encode())

        await git.init(host)
        files = [path for path in await git.untracked_names(host)
                 if "tickets" not in Path(path).parts]
        await git.add(host, files)
        await git.commit(host, "fixture host base", files)
        base_sha = await git.rev_parse(host, "HEAD")

        state = host / ".squatch" / "state"
        pgid: list[int] = []

        def start_serve():
            return asyncio.create_task(self.process.run(
                [sys.executable, "-m", "squatch", "--config", str(host / "config.yaml"),
                 "serve"], cwd=host, env=env, timeout=180, on_spawn=pgid.append))

        serve_task = start_serve()
        merged: dict[str, HostLoopEntry] = {}
        commits: dict[str, str] = {}
        lifecycle = None
        try:
            while len(merged) < 3:
                def next_action(events: tuple[Event, ...]):
                    available = [record for stem, record
                                 in sorted(supervised_merge_holds(events).items())
                                 if stem not in merged]
                    if available:
                        return "hold", available[0]
                    intakes = [event for event in events if event.type == "signal"
                               and event.ticket == STEMS["report-to-regression"]
                               and event.body.get("kind") == "ticket_intake"]
                    authored = any(event.type == "signal"
                                   and event.body.get("kind") == "triage_pass"
                                   and STEMS["report-to-regression"]
                                   in event.body.get("triaged", {}).get("authored", ())
                                   for event in events)
                    if (len(merged) >= 2 and authored and intakes
                            and intakes[-1].body.get("state") == "draft"):
                        return "restart", None
                    return None

                action, _ = await _wait_for(state, next_action)
                kind, hold = action
                if kind == "restart":
                    serve_task.cancel()
                    await asyncio.gather(serve_task, return_exceptions=True)
                    argv = [sys.executable, "-m", "squatch", "--config",
                            str(host / "config.yaml"), "confirm",
                            STEMS["report-to-regression"]]
                    rc, out, err = await self.process.run(
                        argv, cwd=host, env=env, timeout=30)
                    expected = (rc == 0 and "moved from draft to confirmed" in out + err)
                    reconciled = (rc == 2 and "is confirmed and has never run" in out + err)
                    if not (expected or reconciled):
                        raise HostLoopEvidenceError(
                            f"draft promotion through the CLI failed ({rc}): {err or out}")
                    events = tuple(read_events(state))
                    intakes = [event for event in events if event.type == "signal"
                               and event.ticket == STEMS["report-to-regression"]
                               and event.body.get("kind") == "ticket_intake"]
                    if not intakes or intakes[-1].body.get("state") != "confirmed":
                        raise HostLoopEvidenceError("regression ticket did not become confirmed")
                    serve_task = start_serve()
                    continue
                assert kind == "hold"
                assert hold is not None
                lifecycle = hold.lifecycle
                request = ControlRequest(
                    action="confirm", lifecycle=hold.lifecycle, hold_id=hold.hold_id,
                    stem=hold.stem, actor="machine")
                publish_control(state, request, self.fs)

                def admitted(events: tuple[Event, ...]):
                    terminal = next((event for event in events
                                     if event.type == "state_transition"
                                     and event.ticket == hold.stem
                                     and event.body.get("to") == "merged"), None)
                    accepted = next((event for event in events
                                     if event.type == "signal"
                                     and event.key == f"control/{request.request_id}"
                                     and event.body.get("outcome") == "accepted"
                                     and event.body.get("applied") is True), None)
                    release = next((event for event in events
                                    if event.type == "signal"
                                    and event.body.get("kind") == "supervised_merge_release"
                                    and event.body.get("hold_id") == str(hold.hold_id)
                                    and event.body.get("actor") == "machine"), None)
                    return (terminal, accepted, release) if all(
                        item is not None for item in (terminal, accepted, release)) else None

                evidence, _ = await _wait_for(state, admitted)
                terminal, accepted, release = evidence
                run = terminal.body.get("run_seq")
                commit = terminal.body.get("commit")
                if type(run) is not int or run < 0 or not isinstance(commit, str) or not commit:
                    raise HostLoopEvidenceError(f"malformed merged terminal for {hold.stem}")
                commits[hold.stem] = commit
                merged[hold.stem] = HostLoopEntry(
                    member="machine_ticket_merge", scenario=hold.stem,
                    observable=(f"{accepted.key}+{release.key}+merged:{commit}"),
                    producing_run=f"{hold.stem}/{run}")
                if len(merged) == 2:
                    self._publish_report(host, "regression", base_sha)

            regression_entry = merged[STEMS["report-to-regression"]]
            _, events = await _wait_for(state, self._regression_loop)
            regression_pass = next(event for event in events
                                   if self._regression_loop((event,)) is not None)

            escape_commit = commits[STEMS["machine-introduced-escape"]]
            self._publish_report(host, "escape", escape_commit)
            escape_pass, _ = await _wait_for(state, self._escape_loop)
            attributed = await git.escape_tickets(host, escape_commit)
            if attributed != (STEMS["machine-introduced-escape"],):
                raise HostLoopEvidenceError(
                    f"escape commit attribution was {attributed!r}, not the machine ticket")

            head = await git.rev_parse(host, "HEAD")
            ordered = tuple(merged[STEMS[scenario]] for scenario in (
                "deterministic-app", "report-to-regression", "machine-introduced-escape"))
            return HostLoopReport(
                schema_version=1, produced_at_sha=head,
                entries=ordered + (
                    HostLoopEntry(
                        member="report_to_regression_bug_loop",
                        scenario="report-to-regression",
                        observable=(f"{regression_pass.ts}:report-inbox->triage->"
                                    f"{STEMS['report-to-regression']}->merged"),
                        producing_run=regression_entry.producing_run),
                    HostLoopEntry(
                        member="escape_attribution", scenario="machine-introduced-escape",
                        observable=(f"{escape_pass.ts}:first-parent:{escape_commit}:"
                                    f"squatch-ticket={attributed[0]}"),
                        producing_run=merged[attributed[0]].producing_run),
                ))
        finally:
            if not serve_task.done() and lifecycle is not None:
                publish_control(state, ControlRequest(action="kill", lifecycle=lifecycle), self.fs)
                try:
                    await asyncio.wait_for(asyncio.shield(serve_task), timeout=15)
                except (TimeoutError, asyncio.TimeoutError):
                    serve_task.cancel()
            if not serve_task.done():
                serve_task.cancel()
            if serve_task.cancelled() and pgid:
                kill_group(pgid[0])
            await asyncio.gather(serve_task, return_exceptions=True)

    async def _command(self, argv: list[str], cwd: Path,
                       env: Mapping[str, str], *, stdin: Path | None = None) -> str:
        rc, out, err = await self.process.run(
            argv, cwd=cwd, env=env, timeout=30, stdin_path=stdin)
        if rc:
            raise HostLoopEvidenceError(f"{argv!r} exited {rc}: {err or out}")
        return out

    async def _fixture_author(self, host: Path, env: Mapping[str, str], scenario: str) -> dict:
        prompt = host / f".{scenario}.prompt"
        self.fs.write(prompt, ("squatch prompt: surface=author spec_version=1.1\n"
                               f"fixture-scenario: {scenario}\n").encode())
        try:
            output = await self._command([str(host / "bin" / "codex"), "exec", "--json"],
                                         host, env, stdin=prompt)
        finally:
            self.fs.unlink(prompt)
        for line in output.splitlines():
            row = json.loads(line)
            if row.get("type") == "item.completed":
                return json.loads(row["item"]["text"])
        raise HostLoopEvidenceError(f"fixture author returned no artifact for {scenario}")

    def _publish_report(self, host: Path, name: str, app_commit: str) -> None:
        report = json.loads((host / "reports" / f"{name}-report.json").read_text())
        report["app_commit"] = app_commit
        inbox = host / ".squatch" / "report-inbox"
        self.fs.write(inbox / f"{name}.report.json", json.dumps(report).encode())
        self.fs.write(inbox / report["replay_file"],
                      (host / report["replay_file"]).read_bytes())

    @staticmethod
    def _regression_loop(events: tuple[Event, ...]) -> Event | None:
        return next((event for event in events if event.type == "signal"
                     and event.body.get("kind") == "triage_pass"
                     and STEMS["report-to-regression"]
                     in event.body.get("triaged", {}).get("authored", ())), None)

    @staticmethod
    def _escape_loop(events: tuple[Event, ...]) -> Event | None:
        return next((event for event in events if event.type == "signal"
                     and event.body.get("kind") == "triage_pass"
                     and event.body.get("triaged", {}).get("tombstone")), None)


def run(**kwargs) -> HostLoopReport:
    """Synchronous producer entry point; the caller alone may serialize the report."""
    evidence_root = kwargs.pop("evidence_root", None)
    return asyncio.run(FixtureHostLoop(**kwargs).run(evidence_root=evidence_root))
