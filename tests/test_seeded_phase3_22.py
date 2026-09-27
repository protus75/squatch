"""No-code soak producer and terminal Phase 3 continuation contracts."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "soak-run": ("outbox-only-admission",),
    "phase3-continue-23": ("soak-run",),
}
CORRECTION = "outbox-only-admission"
CORRECTION_DEPENDS = ("phase3-continue-22",)
CORRECTION_OWNERSHIP = {
    "owns": ["squatch/stages.py", "squatch/merge.py",
             "tests/test_stages.py", "tests/test_merge.py"],
    "hooks": [],
}
CORRECTION_CONTEXT = ("squatch/stages.py",)
CORRECTION_ON_DEMAND = (
    "squatch/merge.py", "tests/test_stages.py", "tests/test_merge.py",
)
OWNERSHIP = {
    "soak-run": {
        "owns": ["tickets/soak-run/daemon-soak-report.json"], "hooks": [],
    },
    "phase3-continue-23": {
        "owns": ["tickets", "tests/test_seeded_phase3_22.py",
                 "tests/test_seeded_phase3_23.py"], "hooks": [],
    },
}
PREDECESSOR_OWNERSHIP = {
    "soak-run": {
        "owns": ["tickets/soak-run/daemon-soak-report.json"], "hooks": [],
    },
    "phase3-continue-23": {
        "owns": ["tickets", "tests/test_seeded_phase3_23.py"], "hooks": [],
    },
}
CONTEXT = {
    "soak-run": ("eval/daemon_soak.py", "tests/test_daemon_soak_runner.py"),
    "phase3-continue-23": (
        "tests/test_seeded_phase3_11.py", "tests/test_seeded_phase3_22.py",
        "tests/test_serve.py",
    ),
}
ON_DEMAND = {"soak-run": (), "phase3-continue-23": ()}
EXISTING_AT_AUTHORING = {
    "eval/daemon_soak.py": 25471,
    "tests/test_daemon_soak_runner.py": 12245,
    "tests/test_seeded_phase3_11.py": 9238,
    "tests/test_seeded_phase3_22.py": 9154,
    "tests/test_serve.py": 9235,
    "squatch/stages.py": 52958,
}
NEW_PATH_OWNERS = {
    "tickets/soak-run/daemon-soak-report.json": "soak-run",
    "tests/test_seeded_phase3_23.py": "phase3-continue-23",
    "tests/test_phase3_exit.py": "phase3-exit",
    "tests/test_seeded_phase4_core.py": "phase3-exit",
}
FULL = (("soak-run",), ("phase3-exit",))


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO,
        plan=(REPO / PLAN_FILE).read_text(),
        resolve_stem=lambda candidate: _path(candidate).is_file(),
    )


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def _admissions(stem):
    [rows] = [block for block in _yaml(stem) if isinstance(block, list)]
    return tuple(tuple(row) for row in rows)


def test_exact_seeds_edges_tiers_budgets_cap_and_fences():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("soak-run", "phase3-continue-23")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-22")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == PREDECESSOR_OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]

    correction = _ticket(CORRECTION)
    assert (correction.source, correction.state, correction.priority) == (
        "seed", "confirmed", "P1")
    assert correction.depends == CORRECTION_DEPENDS
    assert correction.plan_sections == ("20",)
    assert (correction.agent_tier, correction.agent_effort) == ("high", "high")
    assert (correction.expected_minutes, correction.stuck_minutes) == (90, 180)
    assert correction.scope_fence == tuple(CORRECTION_OWNERSHIP["owns"])
    assert correction.context == CORRECTION_CONTEXT


def test_context_partitions_predecessor_closure_and_new_path_owners():
    observed_owners = {}
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert not ON_DEMAND[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(
            set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                observed_owners[path] = stem
            elif path != "tickets":
                assert path in ticket.context

    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-23")
                   if isinstance(block, dict) and "ownership" in block]
    [contexts] = [block["context"] for block in _yaml("phase3-continue-23")
                  if isinstance(block, dict) and "context" in block]
    assert ownership == {
        "phase3-exit": {
            "owns": ["tickets", "tests/test_phase3_exit.py", "tests/test_seeded_phase4_core.py"],
            "hooks": [],
        },
    }
    assert {stem: tuple(paths) for stem, paths in contexts.items()} == {
        "phase3-exit": (
            "tickets/soak-run/daemon-soak-report.json", "squatch/artifacts.py",
            "eval/daemon_soak.py", "tests/test_daemon_soak_runner.py",
            "tests/test_seeded_phase3_11.py",
        ),
    }
    for path in ownership["phase3-exit"]["owns"]:
        if path != "tickets":
            observed_owners[path] = "phase3-exit"
    assert observed_owners == NEW_PATH_OWNERS

    soak_scope = _section("soak-run", "Scope in")
    for phrase in ("Make no code changes", "merged public deterministic runner",
                   "canonical ordinary-lane writer", "not self-attested",
                   "sole new-path ownership", "schema-validated report"):
        assert phrase in soak_scope

    correction_scope = _section(CORRECTION, "Scope in")
    for path in CORRECTION_ON_DEMAND:
        assert path not in _ticket(CORRECTION).context
        assert f"`{path}`" in correction_scope
    for phrase in ("completed run-scoped lift", "registered in `KNOWN_ARTIFACTS`",
                   "excluding `run.md`", "commit: null", "journal one `merged`"):
        assert phrase in correction_scope
    continuation_scope = _section("phase3-continue-23", "Scope in")
    for phrase in ("predecessor-test closure", "committed report", "evidence custody",
                   "daemon-soak-runner` as machinery", "soak-run` as producer",
                   "sibling-new", "squatch/specs.py"):
        assert phrase in continuation_scope


def test_authoring_sizes_and_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render(
            {"workspace": DataBlock("engine", workspace),
             "ticket": DataBlock("host", _path(stem).read_text()),
             "context": DataBlock("host", context)},
            plan=plan, plan_sections=ticket.plan_sections, effort="max",
        )
        assert len(rendered) <= limit, (stem, len(rendered), limit)

    correction = _ticket(CORRECTION)
    context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                      for path in correction.context)
    workspace = (f"stem: {CORRECTION}\nbranch: {CORRECTION}\n"
                 f"run record: tickets/{CORRECTION}/{RUN_RECORD}\n")
    rendered = spec.render(
        {"workspace": DataBlock("engine", workspace),
         "ticket": DataBlock("host", _path(CORRECTION).read_text()),
         "context": DataBlock("host", context)},
        plan=plan, plan_sections=correction.plan_sections, effort="max",
    )
    assert len(rendered) <= limit, (CORRECTION, len(rendered), limit)

    scope = _section("phase3-continue-23", "Scope in")
    for phrase in ("authoring-time Context sizes", "REQ_RENDER_HEADROOM",
                   "RENDER_BOUND_CHARS['max']"):
        assert phrase in scope


def test_terminal_suffix_exit_custody_and_absence_of_successor():
    assert _admissions("phase3-continue-22") == FULL
    assert _admissions("phase3-continue-23") == (("phase3-exit",),)
    exit_scope = _section("phase3-continue-23", "Scope in")
    assert re.search(r"`phase3-exit`, which depends on\s+`soak-run`", exit_scope)
    assert "KNOWN-HARD high/high" in exit_scope
    assert "There is no successor after `phase3-exit`." in exit_scope
    assert _ticket("phase3-continue-23").depends == ("soak-run",)
