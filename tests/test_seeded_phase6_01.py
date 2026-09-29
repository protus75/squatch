"""Phase 6 contracts pinned at authoring, including the finite terminal suffix.

Context must already be merged at authoring: 02 uses core, 03 uses 01,
and so on, matching the Phase 5 continue-03 -> seeded-01 precedent.
"""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("core-drift-activation", "migrate-config", "phase6-continue-02")
SUFFIX = (
    ROW,
    ("host-contract-doc", "fixture-host-scaffold", "phase6-continue-03"),
    ("bug-gate-grammar", "report-inbox-triage", "phase6-continue-04"),
    ("escape-column", "phase6-continue-05"),
    ("supervised-merge-hold", "phase6-continue-06"),
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"),
    ("phase6-exit",),
)
FENCES = {
    "core-drift-activation": (
        "squatch/hostfiles.py", "squatch/gates.py", "squatch/config.py",
        "squatch/merge.py", "squatch/providers.py", "squatch/__main__.py",
        "tests/test_hostfiles.py", "tests/test_gates.py", "tests/test_merge.py",
        "tests/test_providers.py", "tests/test_cli.py"),
    "migrate-config": (
        "squatch/config.py", "squatch/__main__.py", "tests/test_config.py",
        "tests/test_cli.py", "tests/test_verbs.py"),
    "phase6-continue-02": ("tickets", "tests/test_seeded_phase6_02.py"),
}
CONTEXT = {
    "core-drift-activation": (
        "squatch/hostfiles.py", "squatch/gates.py", "squatch/config.py",
        "tests/test_hostfiles.py"),
    "migrate-config": ("squatch/config.py", "tests/test_config.py"),
    "phase6-continue-02": ("tests/test_seeded_phase6_core.py",),
}
ON_DEMAND = {
    "core-drift-activation": (
        "squatch/merge.py", "squatch/providers.py", "squatch/__main__.py",
        "tests/test_gates.py", "tests/test_merge.py", "tests/test_providers.py",
        "tests/test_cli.py"),
    "migrate-config": ("squatch/__main__.py", "tests/test_cli.py", "tests/test_verbs.py"),
}
REMAINING = {'host-contract-doc': (('migrate-config',),
                       ('docs/host-contract.md', 'tests/test_host_contract.py'),
                       (),
                       ()),
 'fixture-host-scaffold': (('host-contract-doc', 'core-drift-activation'),
                           ('hosts/fixture/', 'tests/test_fixture_host.py'),
                           (),
                           ()),
 'bug-gate-grammar': (('fixture-host-scaffold',),
                      ('squatch/tickets.py',
                       'squatch/gates.py',
                       'squatch/stages.py',
                       'tests/test_tickets.py',
                       'tests/test_gates.py',
                       'tests/test_bug_gate.py'),
                      ('squatch/tickets.py',
                       'squatch/gates.py',
                       'tests/test_tickets.py',
                       'tests/test_gates.py'),
                      ('squatch/stages.py',)),
 'report-inbox-triage': (('bug-gate-grammar',),
                         ('squatch/inbox.py',
                          'squatch/box.py',
                          'squatch/triage.py',
                          'squatch/author.py',
                          'squatch/daemon.py',
                          'tests/test_box.py',
                          'tests/test_triage.py',
                          'tests/test_author.py',
                          'tests/test_inbox.py'),
                         ('squatch/box.py',
                          'squatch/triage.py',
                          'tests/test_box.py',
                          'tests/test_triage.py'),
                         ('squatch/author.py', 'squatch/daemon.py', 'tests/test_author.py')),
 'escape-column': (('bug-gate-grammar', 'report-inbox-triage'),
                   ('squatch/scorecard.py',
                    'squatch/git.py',
                    'tests/test_scorecard.py',
                    'tests/test_git.py'),
                   ('squatch/scorecard.py', 'tests/test_scorecard.py'),
                   ('squatch/git.py', 'tests/test_git.py')),
 'supervised-merge-hold': (('escape-column',),
                           ('squatch/merge.py',
                            'squatch/baseline.py',
                            'squatch/control.py',
                            'squatch/__main__.py',
                            'squatch/stages.py',
                            'squatch/drain.py',
                            'squatch/runner.py',
                            'tests/test_merge.py',
                            'tests/test_baseline.py',
                            'tests/test_control_cli.py',
                            'tests/test_cli.py',
                            'tests/test_drain.py',
                            'tests/test_supervised_merge_hold.py'),
                           (),
                           ('squatch/merge.py',
                            'squatch/baseline.py',
                            'squatch/control.py',
                            'squatch/__main__.py',
                            'squatch/stages.py',
                            'squatch/drain.py',
                            'squatch/runner.py',
                            'tests/test_merge.py',
                            'tests/test_baseline.py',
                            'tests/test_control_cli.py',
                            'tests/test_cli.py',
                            'tests/test_drain.py')),
 'go-grade-machinery': (('supervised-merge-hold', 'fixture-host-scaffold'),
                        ('eval/harness.py',
                         'squatch/artifacts.py',
                         'tests/test_eval_harness.py',
                         'tests/test_go_grade.py'),
                        ('eval/harness.py', 'squatch/artifacts.py', 'tests/test_eval_harness.py'),
                        ()),
 'go-grade-run': (('go-grade-machinery',),
                  ('tickets/go-grade-run/review-baseline-report.json',),
                  ('eval/harness.py', 'squatch/artifacts.py'),
                  ()),
 'exit-receipt-machinery': (('go-grade-run',),
                            ('squatch/artifacts.py',
                             'eval/host_loop.py',
                             'tests/test_host_loop.py',
                             'tests/test_gates.py'),
                            ('squatch/artifacts.py', 'tests/test_gates.py'),
                            ('hosts/fixture/',)),
 'phase6-exit': (('exit-receipt-machinery',),
                 ('tickets/phase6-exit/host-loop-report.json',
                  'tickets/phase6-exit/exit-receipt.json',
                  'tests/test_phase6_exit.py'),
                 (),
                 ())}

BEHAVIOR = {'host-contract-doc': '`host-contract-doc` depends on `migrate-config` and owns/fences new '
                      '`docs/host-contract.md` and new `tests/test_host_contract.py`. It commits '
                      "the section 15 host schema's copyable commented `review`/`merge` example, "
                      'seam inventory, report-inbox contract, managed-file ownership rule, '
                      'migration/cutover steps, and explicitly excludes foreign process-state '
                      'adoption. It has no production-code write and no Context.',
 'fixture-host-scaffold': '`fixture-host-scaffold` depends on both `host-contract-doc` and '
                          '`core-drift-activation` and owns/fences new `hosts/fixture/` plus new '
                          '`tests/test_fixture_host.py`. The fixture contains a host-root config '
                          'profile, miniature deterministic app, replay-runner command, closed '
                          'scenario list, bounded version-1 report fixtures, one merge-base '
                          'regression defect, one machine-introduced escape scenario, and a '
                          'scripted agent-CLI provider row serving Author/Implement/Review at zero '
                          'model spend. It changes no engine module and has no embedded Context: '
                          'sibling-new `docs/host-contract.md` is excluded at authoring and '
                          'becomes an ordinary worktree read after its required '
                          '`host-contract-doc` dependency merges.',
 'bug-gate-grammar': '`bug-gate-grammar` depends on `fixture-host-scaffold` and owns/fences '
                     '`squatch/tickets.py`, `squatch/gates.py`, `squatch/stages.py`, '
                     '`tests/test_tickets.py`, `tests/test_gates.py`, and new '
                     '`tests/test_bug_gate.py`. It adds `kind: bug`, mandatory `## Regression`, '
                     'and the branch-head-pass/merge-base-with-`carries`-overlay- fail hard gate; '
                     'a missing test at base is never accepted as defect evidence. Existing '
                     '`squatch/stages.py` and its composition callers are measured on demand; '
                     'ticket/gate parsers and focused tests are Context.',
 'report-inbox-triage': '`report-inbox-triage` depends on `bug-gate-grammar` and owns/fences new '
                        '`squatch/inbox.py`, `squatch/box.py`, `squatch/triage.py`, '
                        '`squatch/author.py`, `squatch/daemon.py`, `tests/test_box.py`, '
                        '`tests/test_triage.py`, `tests/test_author.py`, and new '
                        '`tests/test_inbox.py`. It enforces the version-1 report schema, '
                        'metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps, copies '
                        'bounded evidence into durable Box custody before recording the message, '
                        'wires the daemon consumer, and makes sequential triage author `kind: bug` '
                        'tickets whose evidence and `## Regression` survive intake. Daemon/Author '
                        'roots and their large tests are measured on-demand exceptions; existing '
                        'Box/Triage seams and focused tests are Context.',
 'escape-column': '`escape-column` depends on both `bug-gate-grammar` and `report-inbox-triage` '
                  'and owns/fences `squatch/scorecard.py`, `squatch/git.py`, '
                  '`tests/test_scorecard.py`, and `tests/test_git.py`. It adds the squash-trailer '
                  'read operation and deterministic bug-to-merged-ticket-or-bounded-range '
                  'attribution, increments escapes only for surfaces that passed the attributed '
                  'merges, and leaves unattributed or foreign history out. `squatch/git.py` and '
                  '`tests/test_git.py` may be measured on demand; scorecard and its test are '
                  'Context.',
 'supervised-merge-hold': '`supervised-merge-hold` is KNOWN-DEEP high/high, depends on '
                          '`escape-column`, and owns/fences `squatch/merge.py`, '
                          '`squatch/baseline.py`, `squatch/control.py`, `squatch/__main__.py`, '
                          '`squatch/stages.py`, `squatch/drain.py`, `squatch/runner.py`, '
                          '`tests/test_merge.py`, `tests/test_baseline.py`, '
                          '`tests/test_control_cli.py`, `tests/test_cli.py`, '
                          '`tests/test_drain.py`, and new `tests/test_supervised_merge_hold.py`. '
                          'It implements the durable HELD admission state after merge safety and '
                          'integration checks but before main mutation, excludes held stems from '
                          'dispatch while preserving their worktrees, releases through '
                          'identity-bound `confirm` without a cap-rearming keep signal, '
                          'rebase/regates against moved main, reconstructs holds on restart, and '
                          'never holds the bootstrap self-build. Every existing production root '
                          'and broad suite in this fence is a measured on-demand exception; the '
                          'new focused test is not Context.',
 'go-grade-machinery': '`go-grade-machinery` depends on both `supervised-merge-hold` and '
                       '`fixture-host-scaffold` and owns/fences `eval/harness.py`, '
                       '`squatch/artifacts.py`, `tests/test_eval_harness.py`, and new '
                       '`tests/test_go_grade.py`. It extends the committed harness to at least 50 '
                       'planted defects under the fixed USD 5.00 cap, runs the harness-local '
                       'Author prompt, records the authored tickets and dependency graph in one '
                       'closed report, and adds operator-only `--record-go`; production '
                       '`specs/author.md` is never used. Existing harness/artifact modules and '
                       '`tests/test_eval_harness.py` are Context.',
 'go-grade-run': '`go-grade-run` depends on `go-grade-machinery`, changes no code, and owns/fences '
                 'only `tickets/go-grade-run/review-baseline-report.json`. It executes the merged '
                 'harness once through the run lane. The committed report embeds its mechanically '
                 'recorded GO-or-NO-GO verdict signal identity; only the operator may turn an '
                 'earned result into GO, so NO-GO is a valid self-build result. Its Context is '
                 '`eval/harness.py` and `squatch/artifacts.py`.',
 'exit-receipt-machinery': '`exit-receipt-machinery` depends on `go-grade-run` and owns/fences '
                           '`squatch/artifacts.py`, new `eval/host_loop.py`, new '
                           '`tests/test_host_loop.py`, and `tests/test_gates.py`. It registers '
                           'closed writers for `host-loop-report.json` and `exit-receipt.json`; '
                           'the host-loop harness launches supervised `serve` as a subprocess '
                           'against `hosts/fixture/`, drives machine-actor confirms through the '
                           'control inbox, and records per-member `(member, driven scenario, '
                           'observable, producing run)` evidence for at least three machine-ticket '
                           'merges, the report-to-regression bug loop, and escape attribution. The '
                           'machinery never produces terminal artifacts during its own build. '
                           'Existing artifact code/tests `squatch/artifacts.py` and '
                           '`tests/test_gates.py` are embedded Context; the directory '
                           '`hosts/fixture/` is a named measured on-demand worktree read and is '
                           'never an embedded Context entry.',
 'phase6-exit': '`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on every '
                "Phase 6 payload, and is the last row's sole KNOWN-HARD high/high seed. It authors "
                'no successor and owns/fences only `tickets/phase6-exit/host-loop-report.json`, '
                '`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`. It '
                'runs the registered host-loop producer, reads the committed GO-grade report and '
                'its embedded verdict identity, accepts GO or NO-GO, proves the three closed '
                'host-loop members, writes the receipt digest, and performs no engine-code edit. '
                'Live-host K>=10 and real-host bug-loop evidence remain operator post-cutover '
                'acceptance and are forbidden as exit inputs. Every fenced path is terminal output '
                'or a new focused test, so it has no Context. It has no successor and no '
                'continuation tail is authored.'}

CONTINUATIONS = {'phase6-continue-03': (('tickets', 'tests/test_seeded_phase6_03.py'),
                        ('tests/test_seeded_phase6_01.py',)),
 'phase6-continue-04': (('tickets', 'tests/test_seeded_phase6_04.py'),
                        ('tests/test_seeded_phase6_02.py',)),
 'phase6-continue-05': (('tickets', 'tests/test_seeded_phase6_05.py'),
                        ('tests/test_seeded_phase6_03.py',)),
 'phase6-continue-06': (('tickets', 'tests/test_seeded_phase6_06.py'),
                        ('tests/test_seeded_phase6_04.py',)),
 'phase6-continue-07': (('tickets', 'tests/test_seeded_phase6_07.py'),
                        ('tests/test_seeded_phase6_05.py',)),
 'phase6-continue-08': (('tickets', 'tests/test_seeded_phase6_08.py'),
                        ('tests/test_seeded_phase6_06.py',))}

CONTINUATION_RULE = ('Every numbered continuation owns only `tickets` plus its matching new '
 '`tests/test_seeded_phase6_<nn>.py`, embeds the immediately preceding merged Phase 6 seeded test '
 'as its sole Context, depends on every payload in its row, pins the exact edges and contracts '
 'plus max-effort headroom, and carries the shrinking suffix. Merged means already on main at '
 'authoring time. The sibling-new seeded test created alongside that continuation is excluded '
 'because new and sibling-new paths are never Context. `phase6-continue-03` passes this same rule '
 'forward for every later numbered continuation.')

ROW_BEHAVIOR = {'core-drift-activation': 'Activate the engine-shipped hard `core_drift` gate on conduct-file '
                          'paths resolved from routing. Compare every committed managed block with '
                          'a fresh branch-version render, preserve the project-owned remainder, '
                          'refuse malformed, duplicate, or partial marker text, and join the '
                          'merge-time mechanical rerun set. Move the complete '
                          'routing-to-conduct-file resolver from inline `_core` logic into one '
                          '`squatch/providers.py` function. Both `_core` and `core_drift` call '
                          'that function; the provider-to-`CLAUDE.md`/`AGENTS.md` mapping has one '
                          'owner and no copied path. Replace '
                          '`test_classifier_is_unreachable_from_production_gates` with coverage '
                          'proving the gate reaches `hostfiles.classify` and both invokers share '
                          'the resolver. Keep `test_rendering_has_no_git_or_commit_effect`; '
                          '`squatch/hostfiles.py` retains its exact pure import set. '
                          '`squatch/merge.py`, `squatch/providers.py`, `squatch/__main__.py`, '
                          '`tests/test_gates.py`, `tests/test_merge.py`, '
                          '`tests/test_providers.py`, and `tests/test_cli.py` are measured '
                          'on-demand inspection exceptions. Every other existing fence path is '
                          'Context. No new Context path is invented.',
 'migrate-config': 'Add only the explicit `migrate-config` verb. The sole supported older schema '
                   'is version 0: its complete key vocabulary, nesting, value types, defaults, and '
                   "meanings are exactly version 1's except for required top-level integer "
                   '`schema_version: 0`. The deterministic 0-to-1 mapping changes only that scalar '
                   'to integer 1 and keeps every other key byte-for-byte; it never resolves auth '
                   'values or changes host intent. Validate the complete candidate through the '
                   'real loader before one atomic replace and retain a recoverable adjacent '
                   'backup. A valid current version-1 file is a byte-identical no-op. Refuse with '
                   'no write a missing or non-integer version, a version below 0 or above 1, an '
                   'unknown key, or input invalid under the version-1 shape after scalar '
                   'substitution. `squatch/__main__.py`, `tests/test_cli.py`, and '
                   '`tests/test_verbs.py` are measured on-demand inspection exceptions; config and '
                   'its focused test are Context.'}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _scope(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _section(stem, name):
    return " ".join(_scope(stem, name).split())


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)\n```", _scope(stem, "Scope in"), re.S) if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)



EXISTING_AT_AUTHORING = {'squatch/hostfiles.py': 11825,
 'squatch/gates.py': 5504,
 'squatch/config.py': 10606,
 'tests/test_hostfiles.py': 5251,
 'tests/test_config.py': 12450,
 'tests/test_seeded_phase6_core.py': 18492}
SECTION_20_CHARS_AT_AUTHORING = 76773


def _paragraphs(stem):
    return tuple(" ".join(part.split())
                 for part in _scope(stem, "Scope in").split("\n\n"))


def _paths(clause):
    return tuple(re.findall(r"`([^`]+)`", clause))


def test_first_row_identity_edges_tiers_citations_fences_and_partitions():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert _admissions("phase6-continue") == SUFFIX
    assert len(ROW) <= config.seeding.max_seeds_per_admission == 3
    dependencies = (("core-drift-classifier",), ("core-renderer",), ROW[:2])
    for stem, depends in zip(ROW, dependencies, strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem]
        assert all((REPO / path).is_file() for path in ticket.context)
    for stem, paths in ON_DEMAND.items():
        assert set(CONTEXT[stem]).isdisjoint(paths)
        assert set(CONTEXT[stem]) | set(paths) == set(FENCES[stem])
        scope = _section(stem, "Scope in")
        clause = re.search(r"((?:`[^`]+`[, ]*(?:and )?)+) are measured on-demand inspection exceptions", scope)
        assert clause, stem
        assert _paths(clause.group(1)) == paths
    assert _ticket("phase6-continue").context == ("tests/test_seeded_phase5_04.py",)
    assert CONTEXT["phase6-continue-02"] == ("tests/test_seeded_phase6_core.py",)
    assert set(CONTEXT["phase6-continue-02"]).isdisjoint({
        "tests/test_seeded_phase6_01.py", "tests/test_seeded_phase6_02.py",
        "squatch/hostfiles.py", "tests/test_hostfiles.py",
    })


def test_first_row_complete_behavior_boundaries():
    for stem, contract in ROW_BEHAVIOR.items():
        assert _section(stem, "Scope in") == contract
    scope = _section("phase6-continue-02", "Scope in")
    assert "It authors row 2" in scope
    assert "Every payload and continuation cites section 20 alone and starts medium/medium" in scope
    assert "unless marked KNOWN-DEEP or KNOWN-HARD high/high" in scope
    assert "Render every authored seed at max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`" in scope
    assert "never render section 19" in scope


def test_remaining_payloads_have_exact_edges_fences_and_complete_behavior():
    paragraphs = _paragraphs("phase6-continue-02")
    for stem, (depends, fence, context, on_demand) in REMAINING.items():
        # Equality pins the entire behavior, including negative and terminal obligations.
        matches = [part for part in paragraphs if part.startswith(f"`{stem}` ")
                   and not part.startswith(f"`{stem}` partition:")]
        assert matches == [BEHAVIOR[stem]], stem
        behavior = matches[0]
        edge = re.search(r"depends on (.*?)(?=,| and owns/fences|\. )", behavior)
        assert edge, stem
        assert _paths(edge.group(1)) == depends
        fence_clause = behavior.split("owns/fences", 1)[1].split(". It", 1)[0]
        assert _paths(fence_clause) == fence, stem
        assert set(context).isdisjoint(on_demand)
        if stem not in {"go-grade-run", "exit-receipt-machinery"}:
            assert set(context) | set(on_demand) <= set(fence)
    assert "`supervised-merge-hold` is KNOWN-DEEP high/high" in BEHAVIOR["supervised-merge-hold"]
    assert "last row's sole KNOWN-HARD high/high seed" in BEHAVIOR["phase6-exit"]


def test_remaining_partitions_are_explicit_and_exclude_new_paths():
    paragraphs = _paragraphs("phase6-continue-02")
    for stem, (_, fence, context, on_demand) in REMAINING.items():
        [clause] = [part for part in paragraphs if part.startswith(f"`{stem}` partition:")]
        embedded, measured = clause.split("Embedded Context: ", 1)[1].split("; measured on-demand: ")
        assert _paths(embedded) == context, stem
        assert _paths(measured) == on_demand, stem
        if not context:
            assert embedded == "none"
        if not on_demand:
            assert measured == "none."
        assert all((REPO / path).is_file() for path in context), stem
        new_paths = set(re.findall(r"new `([^`]+)`", BEHAVIOR[stem]))
        assert new_paths.isdisjoint(set(context) | set(on_demand)), stem
    assert "sibling-new `docs/host-contract.md` is excluded at authoring" in BEHAVIOR["fixture-host-scaffold"]
    assert REMAINING["exit-receipt-machinery"][3] == ("hosts/fixture/",)


def test_continuations_use_one_authoring_time_predecessor_rule_and_shrinking_suffix():
    assert _admissions("phase6-continue-02") == SUFFIX[1:]
    scope = _section("phase6-continue-02", "Scope in")
    assert CONTINUATION_RULE in scope
    assert "`tests/test_seeded_phase6_01.py` was sibling-new when this continuation was authored" in scope
    paragraphs = _paragraphs("phase6-continue-02")
    for row in SUFFIX[1:-1]:
        stem = row[-1]
        fence, context = CONTINUATIONS[stem]
        [clause] = [part for part in paragraphs if part.startswith(f"`{stem}` depends on ")]
        edge, custody = clause.split(". It owns only ")
        assert _paths(edge) == (stem, *row[:-1])
        owned, embedded = custody.split(" and has sole Context ")
        assert _paths(owned) == fence
        assert _paths(embedded) == context
        number = int(stem.rsplit("-", 1)[1])
        assert context == (f"tests/test_seeded_phase6_{number - 2:02d}.py",)
        assert f"tests/test_seeded_phase6_{number - 1:02d}.py" not in context
    assert len(CONTINUATIONS) == 6


def test_terminal_row_custody_and_no_successor():
    assert SUFFIX[-1] == ("phase6-exit",)
    assert REMAINING["phase6-exit"] == (
        ("exit-receipt-machinery",),
        ("tickets/phase6-exit/host-loop-report.json",
         "tickets/phase6-exit/exit-receipt.json", "tests/test_phase6_exit.py"), (), (),
    )
    scope = _section("phase6-continue-02", "Scope in")
    assert "The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail" in scope
    assert "phase6-continue-09" not in scope
    assert not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_every_authored_seed_renders_at_max_effort_with_section20_only():
    spec = load_spec(REPO / "specs" / "implement.md")
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in ROW:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\n"
                                   f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context),
        }, plan=_authoring_plan(), plan_sections=ticket.plan_sections, effort="max")
        assert ticket.plan_sections == ("20",)
        assert "## 19. Implementation phases" not in rendered
        assert len(rendered) <= limit, (stem, len(rendered), limit)
