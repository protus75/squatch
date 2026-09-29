"""Phase 6 core admission and the fixed finite continuation registry."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
CORE = {
    "core-renderer": ("phase5-exit",),
    "core-drift-classifier": ("core-renderer",),
    "phase6-continue": ("core-renderer", "core-drift-classifier"),
}
OWNERSHIP = {
    "core-renderer": (
        "squatch/hostfiles.py", "tests/test_hostfiles.py", "squatch/__main__.py",
        "tests/test_cli.py", "tests/test_verbs.py",
    ),
    "core-drift-classifier": ("squatch/hostfiles.py", "tests/test_hostfiles.py"),
    "phase6-continue": ("tickets", "tests/test_seeded_phase6_01.py"),
}
CONTEXT = {
    "core-renderer": (),
    "core-drift-classifier": (),
    "phase6-continue": ("tests/test_seeded_phase5_04.py",),
}
EXISTING_AT_AUTHORING = {"tests/test_seeded_phase5_04.py": 7161}
SECTION_20_CHARS_AT_AUTHORING = 65843
CORE_ON_DEMAND = {
    "core-renderer": {
        "squatch/__main__.py": 30344,
        "tests/test_cli.py": 24700,
        "tests/test_verbs.py": 12471,
    },
    "core-drift-classifier": {},
    "phase6-continue": {},
}
SUFFIX = (
    ("core-drift-activation", "migrate-config", "phase6-continue-02"),
    ("host-contract-doc", "fixture-host-scaffold", "phase6-continue-03"),
    ("bug-gate-grammar", "report-inbox-triage", "phase6-continue-04"),
    ("escape-column", "phase6-continue-05"),
    ("supervised-merge-hold", "phase6-continue-06"),
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"),
    ("phase6-exit",),
)
EXIT_CONTEXT = (
    "tests/test_retro_box.py", "tests/test_baseline.py", "tests/test_seeded_phase5_03.py",
)
EXIT_CONTEXT_SIZES = {
    "tests/test_retro_box.py": 29874,
    "tests/test_baseline.py": 5086,
    "tests/test_seeded_phase5_03.py": 7980,
}
REMAINING = {
    "core-drift-activation": {
        "marker": "`core-drift-activation` depends",
        "depends": ("`core-drift-classifier`",),
        "fence": ("squatch/hostfiles.py", "squatch/gates.py", "squatch/config.py",
                  "squatch/merge.py", "tests/test_hostfiles.py", "tests/test_gates.py",
                  "tests/test_merge.py"),
        "partition": ("Existing `squatch/merge.py` and `tests/test_merge.py` are measured on-demand exceptions",
                      "every other existing fence path is Context"),
        "behavior": ("engine-shipped hard `core_drift` gate", "fresh branch-version render",
                     "merge-time mechanical rerun set"),
    },
    "migrate-config": {
        "marker": "`migrate-config` depends",
        "depends": ("`core-renderer`",),
        "fence": ("squatch/config.py", "squatch/__main__.py", "tests/test_config.py",
                  "tests/test_cli.py", "tests/test_verbs.py"),
        "partition": ("CLI roots and tests are measured on-demand exceptions",
                      "config and its focused test are Context"),
        "behavior": ("read one older supported schema", "recoverable adjacent backup",
                     "refuse current, future, unknown, or invalid input with no write"),
    },
    "host-contract-doc": {
        "marker": "`host-contract-doc` depends",
        "depends": ("`migrate-config`",),
        "fence": ("docs/host-contract.md", "tests/test_host_contract.py"),
        "partition": ("no production-code write and no Context",),
        "behavior": ("copyable commented `review`/`merge` example", "report-inbox contract",
                     "excludes foreign process-state adoption"),
    },
    "fixture-host-scaffold": {
        "marker": "`fixture-host-scaffold` depends",
        "depends": ("`host-contract-doc`", "`core-drift-activation`"),
        "fence": ("hosts/fixture/", "tests/test_fixture_host.py"),
        "partition": ("`docs/host-contract.md` is its sole Context",),
        "behavior": ("bounded version-1 report fixtures", "one merge-base regression defect",
                     "zero model spend"),
    },
    "bug-gate-grammar": {
        "marker": "`bug-gate-grammar` depends",
        "depends": ("`fixture-host-scaffold`",),
        "fence": ("squatch/tickets.py", "squatch/gates.py", "squatch/stages.py",
                  "tests/test_tickets.py", "tests/test_gates.py", "tests/test_bug_gate.py"),
        "partition": ("`squatch/stages.py` and its composition callers are measured on demand",
                      "ticket/gate parsers and focused tests are Context"),
        "behavior": ("`kind: bug`", "mandatory `## Regression`",
                     "missing test at base is never accepted as defect evidence"),
    },
    "report-inbox-triage": {
        "marker": "`report-inbox-triage` depends",
        "depends": ("`bug-gate-grammar`",),
        "fence": ("squatch/inbox.py", "squatch/box.py", "squatch/triage.py",
                  "squatch/author.py", "squatch/daemon.py", "tests/test_box.py",
                  "tests/test_triage.py", "tests/test_author.py", "tests/test_inbox.py"),
        "partition": ("Daemon/Author roots and their large tests are measured on-demand exceptions",
                      "existing Box/Triage seams and focused tests are Context"),
        "behavior": ("metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps",
                     "durable Box custody before recording the message", "survive intake"),
    },
    "escape-column": {
        "marker": "`escape-column` depends",
        "depends": ("`bug-gate-grammar`", "`report-inbox-triage`"),
        "fence": ("squatch/scorecard.py", "squatch/git.py", "tests/test_scorecard.py",
                  "tests/test_git.py"),
        "partition": ("`squatch/git.py` and `tests/test_git.py` may be measured on demand",
                      "scorecard and its test are Context"),
        "behavior": ("squash-trailer read operation", "increments escapes only for surfaces",
                     "leaves unattributed or foreign history out"),
    },
    "supervised-merge-hold": {
        "marker": "`supervised-merge-hold` is KNOWN-DEEP",
        "depends": ("`escape-column`",),
        "fence": ("squatch/merge.py", "squatch/baseline.py", "squatch/control.py",
                  "squatch/__main__.py", "squatch/stages.py", "squatch/drain.py",
                  "squatch/runner.py", "tests/test_merge.py", "tests/test_baseline.py",
                  "tests/test_control_cli.py", "tests/test_cli.py", "tests/test_drain.py",
                  "tests/test_supervised_merge_hold.py"),
        "partition": ("Every existing production root and broad suite in this fence is a measured on-demand exception",
                      "new focused test is not Context"),
        "behavior": ("durable HELD admission state", "identity-bound `confirm`",
                     "never holds the bootstrap self-build"),
    },
    "go-grade-machinery": {
        "marker": "`go-grade-machinery` depends",
        "depends": ("`supervised-merge-hold`", "`fixture-host-scaffold`"),
        "fence": ("eval/harness.py", "squatch/artifacts.py", "tests/test_harness.py",
                  "tests/test_go_grade.py"),
        "partition": ("Existing harness/artifact modules and `tests/test_harness.py` are Context",),
        "behavior": ("at least 50 planted defects", "fixed USD 5.00 cap",
                     "production `specs/author.md` is never used"),
    },
    "go-grade-run": {
        "marker": "`go-grade-run` depends",
        "depends": ("`go-grade-machinery`",),
        "fence": ("tickets/go-grade-run/review-baseline-report.json",),
        "partition": ("Its Context is `eval/harness.py` and `squatch/artifacts.py`",),
        "behavior": ("changes no code", "GO-or-NO-GO verdict signal identity",
                     "NO-GO is a valid self-build result"),
    },
    "exit-receipt-machinery": {
        "marker": "`exit-receipt-machinery` depends",
        "depends": ("`go-grade-run`",),
        "fence": ("squatch/artifacts.py", "eval/host_loop.py", "tests/test_host_loop.py",
                  "tests/test_artifacts.py"),
        "partition": ("existing artifact code/tests and `hosts/fixture/` are Context",),
        "behavior": ("launches supervised `serve` as a subprocess", "at least three machine-ticket merges",
                     "never produces terminal artifacts during its own build"),
    },
    "phase6-exit": {
        "marker": "`phase6-exit` depends",
        "depends": ("`exit-receipt-machinery`",),
        "fence": ("tickets/phase6-exit/host-loop-report.json",
                  "tickets/phase6-exit/exit-receipt.json", "tests/test_phase6_exit.py"),
        "partition": ("Every fenced path is terminal output or a new focused test, so it has no Context",),
        "behavior": ("accepts GO or NO-GO", "writes the receipt digest",
                     "forbidden as exit inputs"),
    },
}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((index for index in range(start, len(lines))
                if lines[index].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)
        if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _context(paths, sizes):
    return "".join(f"### {path}\n{'x' * sizes[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def _remaining_segments():
    scope = " ".join(_section("phase6-continue", "Scope in").split())
    starts = [(stem, scope.index(contract["marker"]))
              for stem, contract in REMAINING.items()]
    return {
        stem: scope[start:(starts[index + 1][1] if index + 1 < len(starts) else len(scope))]
        for index, (stem, start) in enumerate(starts)
    }


def _owned_paths(segment):
    match = re.search(
        r"owns/fences(?: only)? (.*?)(?=\. (?:It|The|Existing|CLI|Daemon|Every))",
        segment,
    )
    assert match, segment
    return tuple(value for value in re.findall(r"`([^`]+)`", match.group(1))
                 if "/" in value)


def test_exact_core_identities_edges_tiers_citations_fences_and_cap():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(CORE) == ("core-renderer", "core-drift-classifier", "phase6-continue")
    assert len(CORE) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in CORE.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == OWNERSHIP[stem]


def test_context_partition_uses_only_merged_predecessor_and_excludes_new_paths():
    forbidden = {
        "tests/test_seeded_phase6_core.py", "squatch/hostfiles.py",
        "tests/test_hostfiles.py", "tests/test_seeded_phase6_01.py",
    }
    for stem in CORE:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context).isdisjoint(forbidden)
        for path in ticket.context:
            assert (REPO / path).is_file()
            assert DATA_MARKER not in (REPO / path).read_text()
    assert CONTEXT["phase6-continue"] == ("tests/test_seeded_phase5_04.py",)
    for stem, paths in CORE_ON_DEMAND.items():
        scope = " ".join(_section(stem, "Scope in").split())
        for path, size in paths.items():
            assert f"`{path}` ({size} bytes)" in scope
    assert "There is no embedded Context" in _section("core-renderer", "Scope in")
    assert "There is no embedded Context and no on-demand exception" in _section(
        "core-drift-classifier", "Scope in")


def test_exact_remaining_rows_known_deep_terminal_and_no_successor():
    assert _admissions("phase6-continue") == SUFFIX
    assert all(1 <= len(row) <= 3 for row in SUFFIX)
    assert SUFFIX[-1] == ("phase6-exit",)
    scope = " ".join(_section("phase6-continue", "Scope in").split())
    assert "`supervised-merge-hold` is KNOWN-DEEP" in scope
    assert "has no successor" in scope
    assert "phase6-continue-09" not in scope
    assert not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


def test_every_remaining_payload_has_exact_edges_fence_partition_and_behavior():
    segments = _remaining_segments()
    assert tuple(segments) == tuple(REMAINING)
    for stem, contract in REMAINING.items():
        segment = segments[stem]
        assert _owned_paths(segment) == contract["fence"]
        for dependency in contract["depends"]:
            assert dependency in segment.split("owns/fences", 1)[0]
        for phrase in contract["partition"] + contract["behavior"]:
            assert phrase in segment, (stem, phrase)


def test_every_continuation_direct_edge_and_custody_is_pinned():
    scope = " ".join(_section("phase6-continue", "Scope in").split())
    edges = {
        "phase6-continue-02": ("core-drift-activation", "migrate-config"),
        "phase6-continue-03": ("host-contract-doc", "fixture-host-scaffold"),
        "phase6-continue-04": ("bug-gate-grammar", "report-inbox-triage"),
        "phase6-continue-05": ("escape-column",),
        "phase6-continue-06": ("supervised-merge-hold",),
        "phase6-continue-07": ("go-grade-machinery", "go-grade-run"),
        "phase6-continue-08": ("exit-receipt-machinery",),
    }
    for continuation, dependencies in edges.items():
        pattern = rf"`{continuation}` depends on (.*?)(?:\. It authors)"
        [dependency_text] = re.findall(pattern, scope)
        assert all(f"`{dependency}`" in dependency_text for dependency in dependencies)
        assert len(re.findall(r"`[^`]+`", dependency_text)) == len(dependencies)
    assert "Each numbered continuation owns only `tickets` plus its matching new `tests/test_seeded_phase6_<nn>.py`" in scope
    assert "embeds the immediately preceding merged Phase 6 seeded test as its sole Context" in scope
    assert "terminal output or a new focused test, so it has no Context" in scope


def test_renderer_classifier_and_continuation_contracts_are_closed():
    renderer = " ".join(_section("core-renderer", "Scope in").split())
    for phrase in (
        "zero marker-like text", "preserving every project-owned byte",
        "Malformed, partial, or duplicate marker-like text refuses",
        "byte-idempotent", "performs no Git operation", "makes no commit",
        "`squatch/__main__.py`", "`tests/test_cli.py`", "`tests/test_verbs.py`",
    ):
        assert phrase in renderer

    classifier = " ".join(_section("core-drift-classifier", "Scope in").split())
    assert "`missing | current | drifted | refused`" in classifier
    assert "makes no write" in classifier
    assert "unreachable from production gates" in classifier

    continuation = " ".join(_section("phase6-continue", "Scope in").split())
    for phrase in (
        "section 20 alone", "`tests/test_seeded_phase5_04.py`",
        "same-admission `tests/test_seeded_phase6_core.py`",
        "sibling-new `squatch/hostfiles.py` and `tests/test_hostfiles.py`",
        "no historical or live section 19 render is accepted",
        "RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM",
    ):
        assert phrase in continuation


def test_exit_and_all_phase6_core_seeds_render_at_max_effort_with_section20_only():
    assert SECTION_20_CHARS_AT_AUTHORING == 65843
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    render_cases = [("phase5-exit", EXIT_CONTEXT, EXIT_CONTEXT_SIZES)] + [
        (stem, CONTEXT[stem], EXISTING_AT_AUTHORING) for stem in CORE
    ]
    for stem, paths, sizes in render_cases:
        ticket = _ticket(stem)
        assert ticket.plan_sections == ("20",)
        rendered = spec.render({
            "workspace": DataBlock(
                "engine", f"stem: {stem}\nbranch: {stem}\n"
                f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(paths, sizes)),
        }, plan=plan, plan_sections=("20",), effort="max")
        assert "## 19." not in rendered
        assert len(rendered) <= limit, (stem, len(rendered), limit)
