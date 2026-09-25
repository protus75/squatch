"""Run the cumulative shakeout battery or validate its committed report."""

import argparse
import asyncio
import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

from eval.shakeout import registry
from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.audit import audit_journal
from squatch.git import Git
from squatch.llm import FakeLLM
from squatch.providers import child_env
from squatch.seams import SubprocessExec
from squatch.shakeout import (REPORT_NAME, Entry, ShakeoutReport, dumps,
                              dumps_entries)

GIT_TIMEOUT = 60.0


class _Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(microseconds=1)
        return self.now


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m eval.shakeout")
    sub = parser.add_subparsers(dest="verb", required=True)
    run = sub.add_parser("run", help="run all registered groups and write a report")
    run.add_argument("--outbox", required=True, type=Path)
    run.add_argument("--prior", type=Path)
    check = sub.add_parser("check", help="validate a report against the registered members")
    check.add_argument("report", type=Path)
    return parser


def _members(module: str | ModuleType) -> tuple[Member, ...]:
    loaded = importlib.import_module(module) if isinstance(module, str) else module
    members = getattr(loaded, "MEMBERS", None)
    if not isinstance(members, tuple) or not all(isinstance(item, Member) for item in members):
        raise ValueError(f"{loaded.__name__}.MEMBERS must be a tuple of Member values")
    return members


def _registered() -> tuple[tuple[str, tuple[Member, ...]], ...]:
    groups = tuple((stem, _members(module)) for stem, module in registry.GROUPS)
    stems = [stem for stem, _ in groups]
    if len(stems) != len(set(stems)):
        raise ValueError("GROUPS contains a duplicate group stem")
    for stem, members in groups:
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError(f"group {stem} contains a duplicate member name")
    return groups


def _load(path: Path) -> ShakeoutReport:
    return ShakeoutReport.model_validate_json(path.read_bytes())


def _invoking_head() -> str:
    git = Git(SubprocessExec(), env=child_env(dict(os.environ), set()), timeout=GIT_TIMEOUT)
    return asyncio.run(git.rev_parse(Path.cwd(), "HEAD"))


def _run(args) -> int:
    groups = _registered()
    prior = _load(args.prior) if args.prior is not None else None
    entries: list[Entry] = []
    produced_at_sha = _invoking_head()
    with tempfile.TemporaryDirectory(prefix="squatch-shakeout-") as root:
        for group, members in groups:
            for member in members:
                member_id = f"{group}.{member.name}"
                bench = Bench.make(Path(root) / member_id, fake=FakeLLM(), clock=_Clock())
                observed = member.run(bench)
                auditor = "red" if audit_journal(bench.state_dir) else "green"
                entry = Entry(
                    member=member_id, group=group, fault=member.fault,
                    observable=member.observable, expected=member.expected,
                    observed=observed, detail=member.detail,
                    producing_run=bench.producing_run, auditor=auditor,
                    green=observed == member.expected and auditor == "green")
                entries.append(entry)

    if prior is not None:
        for group, _ in groups[:-1]:
            fresh = [entry for entry in entries if entry.group == group]
            old = [entry for entry in prior.entries if entry.group == group]
            if dumps_entries(fresh) != dumps_entries(old):
                differing = next(
                    (left.member for left, right in zip(fresh, old) if left != right),
                    fresh[len(old)].member if len(fresh) > len(old) else
                    old[len(fresh)].member if len(old) > len(fresh) else f"{group}.*")
                print(f"double gate refused: {differing} differs from the prior report")
                return 1

    report = ShakeoutReport(schema_version=1, produced_at_sha=produced_at_sha,
                            groups=tuple(group for group, _ in groups),
                            entries=tuple(entries))
    args.outbox.mkdir(parents=True, exist_ok=True)
    (args.outbox / REPORT_NAME).write_text(dumps(report))
    return 0 if all(entry.green for entry in entries) else 1


def _check(args) -> int:
    report = _load(args.report)
    by_member = {entry.member: entry for entry in report.entries}
    registered = _registered()
    passed = report.groups == tuple(group for group, _ in registered)
    for group, members in registered:
        for member in members:
            name = f"{group}.{member.name}"
            entry = by_member.get(name)
            green = entry is not None and entry.green
            print(f"{name}: {'green' if green else 'red'}")
            passed = passed and green
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args) if args.verb == "run" else _check(args)
    except Exception as error:
        print(f"refused: shakeout {args.verb}: {error}", file=sys.stderr)
        print("  paved road: repair the named registry, report, or checkout input and re-run",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
