"""tickets.py: the section 13 ticket contract and the Phase 1 runner intake
(SQUATCH_PLAN.md sections 13, 19).

Lint tests drive `lint_ticket` on text; intake tests drive `Intake` against a
real temp repo through the real process seam, because "validates and commits"
is a claim about git state.
"""

import asyncio
import os
import textwrap
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest

from squatch.__main__ import main
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.tickets import (CODE, PLAN_FILE, Intake, Ticket, TicketLintError, lint_ticket,
                             parse_frontmatter)

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)

PLAN = textwrap.dedent("""\
    # squatch plan

    ## 11. Failure spine

    Spine prose.

    ## 13. Ticket contract

    Contract prose.
    """)

GOOD = textwrap.dedent("""\
    ---
    priority: P1
    kind: feature
    ---
    ## Depends on
    - none

    ## Context
    - squatch/existing.py

    ## Plan contract
    - section 13

    ## Goal
    The widget parser lands and its test passes.

    ## Why
    The next ticket consumes the parser.

    ## Scope in
    The parser module and its test.

    ## Scope out
    The renderer stays untouched.

    ## Scope fence
    - squatch/widget.py
    - tests/test_widget.py

    ## Acceptance criteria
    - `uv run pytest tests/test_widget.py` exits 0.
    - `squatch/widget.py` exists after merge.

    ## Verification
    ```
    uv run pytest tests/test_widget.py
    ```

    ## Definition of rejected
    Stop if the parser needs a new dependency.

    ## Time budget
    - expected: 20m
    - stuck: 40m
    """)


def clock():
    return T0


def _git_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
        "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test",
    }


@pytest.fixture
def repo(tmp_path):
    """A committed repo holding the plan and one existing Context file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / PLAN_FILE).write_text(PLAN)
    (repo / "squatch").mkdir()
    (repo / "squatch" / "existing.py").write_text("")
    (repo / "specs").mkdir()
    (repo / "specs" / "review.md").write_text("---\n---\n")
    return repo


def lint(text: str, repo: Path, *, stem="widget-parser", resolve=lambda s: False) -> Ticket:
    return lint_ticket(text, stem=stem, repo=repo, plan=PLAN, resolve_stem=resolve)


def refusal(text: str, repo: Path, **kw) -> TicketLintError:
    with pytest.raises(TicketLintError) as e:
        lint(text, repo, **kw)
    err = e.value
    assert err.findings, "a refusal names at least one finding"
    for f in err.findings:
        assert f.code == CODE and f.paved_road.strip(), "every finding ships a paved road"
    return err


def messages(err: TicketLintError) -> str:
    return "\n".join(f"{f.message} || {f.paved_road}" for f in err.findings)


def with_frontmatter(text: str, extra: str) -> str:
    return text.replace("kind: feature\n", f"kind: feature\n{extra}\n", 1)


def with_section(text: str, name: str, body: str) -> str:
    """Replace one `## name` section's body."""
    head, _, rest = text.partition(f"## {name}\n")
    _, nl, tail = rest.partition("\n## ")
    return f"{head}## {name}\n{body}\n" + (f"\n## {tail}" if nl else "")


# --- frontmatter ---------------------------------------------------------------

def test_valid_ticket_lints_with_defaults(repo):
    t = lint(GOOD, repo)
    assert t.stem == "widget-parser"
    assert (t.priority, t.kind) == ("P1", "feature")
    assert (t.agent_tier, t.agent_effort) == ("medium", "medium")
    assert t.state is None and t.source is None and t.gate_bypass == ()
    assert t.depends == () and t.context == ("squatch/existing.py",)
    assert t.plan_sections == ("13",)
    assert t.goal == "The widget parser lands and its test passes."
    assert t.scope_fence == ("squatch/widget.py", "tests/test_widget.py")
    assert t.verification == (("uv", "run", "pytest", "tests/test_widget.py"),)
    assert (t.expected_minutes, t.stuck_minutes) == (20, 40)


def test_unknown_frontmatter_key_is_refused_with_the_closed_key_list(repo):
    err = refusal(with_frontmatter(GOOD, "tags: [parser]"), repo)
    assert "tags" in messages(err) and "gate_bypass" in messages(err)


@pytest.mark.parametrize("line", [
    "priority: P4", "kind: refactor", "state: running", "agent_tier: ultra",
    "agent_effort: 7", "source: nobody", "source: box", "gate_bypass: [scope_fence]",
    "gate_bypass: [{code: nope, reason: x}]",
])
def test_out_of_vocabulary_frontmatter_value_is_refused(repo, line):
    key = line.split(":")[0]
    text = GOOD.replace(f"{key}: ", f"{key}_x: ", 1) if key in ("priority", "kind") else GOOD
    err = refusal(with_frontmatter(text, line), repo)
    assert key in messages(err)


def test_kind_and_priority_are_never_inferred(repo):
    err = refusal(GOOD.replace("kind: feature\n", ""), repo)
    assert "kind" in messages(err)
    err = refusal(GOOD.replace("priority: P1\n", ""), repo)
    assert "priority" in messages(err)
    # A bare `key:` is YAML null, not a value: as missing as no key at all.
    err = refusal(GOOD.replace("priority: P1\nkind: feature\n", "priority:\nkind:\n"), repo)
    assert "priority" in messages(err) and "kind" in messages(err)


@pytest.mark.parametrize("line", [
    "priority: [P1]", "kind: {bug: true}", "state: [confirmed]", "agent_tier: [high]",
    "agent_effort: {}", "source: [human]", "gate_bypass: [{code: [diff_budget], reason: x}]",
])
def test_non_string_frontmatter_value_is_refused_not_crashed(repo, line):
    key = line.split(":")[0]
    text = GOOD.replace(f"{key}: ", f"{key}_x: ", 1) if key in ("priority", "kind") else GOOD
    assert key in messages(refusal(with_frontmatter(text, line), repo))


def test_gate_bypass_entries_parse(repo):
    t = lint(with_frontmatter(
        GOOD, "gate_bypass:\n  - {code: diff_budget, reason: generated fixture}"), repo)
    assert t.gate_bypass == (("diff_budget", "generated fixture"),)


def test_missing_or_unterminated_frontmatter_is_refused(repo):
    assert "frontmatter" in messages(refusal(GOOD.split("---\n", 2)[2], repo))
    assert "frontmatter" in messages(refusal("---\npriority: P1\n" + GOOD.split("---\n", 2)[2], repo))


def test_parse_frontmatter_is_safe_load_shaped():
    meta, body = parse_frontmatter("---\na: 1\n---\nbody\n")
    assert meta == {"a": 1} and body == ["body"]


# --- stems ---------------------------------------------------------------------

@pytest.mark.parametrize("stem", ["Widget", "a", "-abc", "a_b", "x" * 65, "decisions", "retro"])
def test_stem_outside_the_grammar_or_reserved_is_refused(repo, stem):
    err = refusal(GOOD, repo, stem=stem)
    assert stem in messages(err)


# --- body sections -------------------------------------------------------------

def test_missing_required_section_is_refused(repo):
    text = GOOD.replace("## Time budget\n- expected: 20m\n- stuck: 40m\n", "")
    assert "Time budget" in messages(refusal(text, repo))


def test_unknown_or_duplicate_section_is_refused(repo):
    assert "Notes" in messages(refusal(GOOD + "\n## Notes\nhi\n", repo))
    assert "twice" in messages(refusal(GOOD + "\n## Why\nagain\n", repo))


def test_depends_resolves_only_against_known_stems(repo):
    text = with_section(GOOD, "Depends on", "- parser-core\n- ghost")
    err = refusal(text, repo, resolve=lambda s: s == "parser-core")
    assert "ghost" in messages(err) and "parser-core" not in messages(err)
    t = lint(with_section(GOOD, "Depends on", "- parser-core"), repo, resolve=lambda s: True)
    assert t.depends == ("parser-core",)


def test_depends_prose_ordering_is_not_a_grammar(repo):
    err = refusal(with_section(GOOD, "Depends on", "after the parser lands"), repo)
    assert "Depends on" in messages(err)


def test_context_path_must_exist(repo):
    err = refusal(with_section(GOOD, "Context", "- squatch/missing.py"), repo)
    assert "squatch/missing.py" in messages(err)


def test_context_refuses_the_plan_file_naming_the_plan_contract_road(repo):
    err = refusal(with_section(GOOD, "Context", f"- {PLAN_FILE}"), repo)
    (f,) = err.findings
    assert PLAN_FILE in f.message and "Plan contract" in f.paved_road


def test_context_refuses_prompt_spec_files(repo):
    err = refusal(with_section(GOOD, "Context", "- specs/review.md"), repo)
    assert "Plan contract" in messages(err)


def test_context_refuses_paths_outside_the_repo(repo):
    err = refusal(with_section(GOOD, "Context", "- ../outside.py"), repo)
    assert "../outside.py" in messages(err)
    err = refusal(with_section(GOOD, "Context", f"- {repo}/squatch/existing.py"), repo)
    assert "repo-relative" in messages(err)


def test_plan_contract_unresolvable_section_id_is_refused(repo):
    err = refusal(with_section(GOOD, "Plan contract", "- section 99"), repo)
    assert "99" in messages(err)


def test_plan_contract_non_section_id_form_is_refused(repo):
    err = refusal(with_section(GOOD, "Plan contract", "- the failure spine"), repo)
    assert "section" in messages(err).lower()


def test_plan_contract_deduplicates_and_is_optional(repo):
    t = lint(with_section(GOOD, "Plan contract", "- section 11\n- section 13\n- section 11"), repo)
    assert t.plan_sections == ("11", "13")
    text = GOOD.replace("## Plan contract\n- section 13\n\n", "")
    assert lint(text, repo).plan_sections == ()


def test_plan_contract_is_required_on_a_seed(repo):
    text = with_frontmatter(GOOD, "source: seed").replace("## Plan contract\n- section 13\n\n", "")
    assert "seed" in messages(refusal(text, repo))


def test_scope_fence_is_one_prefix_per_bullet(repo):
    assert "Scope fence" in messages(refusal(with_section(GOOD, "Scope fence", "everything"), repo))


def test_verification_is_a_fenced_argv_block(repo):
    assert "fenced" in messages(refusal(with_section(GOOD, "Verification", "run the tests"), repo))
    err = refusal(with_section(GOOD, "Verification", "```\nuv run pytest 'unbalanced\n```"), repo)
    assert "unbalanced" in messages(err)
    err = refusal(with_section(GOOD, "Verification", "```\nuv run pytest | tee out.txt\n```"), repo)
    assert "shell" in messages(err)


def test_acceptance_criteria_must_be_checkable(repo):
    err = refusal(with_section(GOOD, "Acceptance criteria", "- The parser is robust."), repo)
    assert "Verification" in messages(err)


@pytest.mark.parametrize("word", ["improved", "better", "cleaner"])
def test_banned_adjectives_fail_lint(repo, word):
    text = with_section(GOOD, "Acceptance criteria",
                        f"- `uv run pytest tests/test_widget.py` is {word} than before.")
    assert word in messages(refusal(text, repo))


def test_regression_present_exactly_when_kind_is_bug(repo):
    bug = GOOD.replace("kind: feature", "kind: bug")
    assert "Regression" in messages(refusal(bug, repo))
    regression = "```\nuv run pytest tests/test_widget.py -k repro\n```\n- carries: tests/test_widget.py"
    t = lint(with_section(bug, "Time budget", "- expected: 20m\n- stuck: 40m\n\n## Regression\n"
                          + regression), repo)
    assert t.regression.command == ("uv", "run", "pytest", "tests/test_widget.py", "-k", "repro")
    assert t.regression.carries == ("tests/test_widget.py",)
    err = refusal(with_section(GOOD, "Time budget", "- expected: 20m\n- stuck: 40m\n\n## Regression\n"
                               + regression), repo)
    assert "kind: bug" in messages(err)


def test_time_budget_grammar(repo):
    for body in ("- expected: 20m", "- expected: 20m\n- stuck: soon", "- expected: 2h\n- stuck: 40m",
                 "about an hour"):
        assert "Time budget" in messages(refusal(with_section(GOOD, "Time budget", body), repo))


def test_exit_read_window_is_optional_and_closed_form(repo):
    text = GOOD + "\n## Exit-read window\n- state_transition: to merged for stem widget-parser\n"
    t = lint(text, repo)
    assert t.exit_read_window == (("state_transition", "to merged for stem widget-parser"),)
    err = refusal(GOOD + "\n## Exit-read window\n- everything after tuesday\n", repo)
    assert "Exit-read window" in messages(err)


def test_all_defects_are_reported_at_once(repo):
    text = with_frontmatter(with_section(GOOD, "Context", f"- {PLAN_FILE}"), "tags: [x]")
    err = refusal(text.replace("- stuck: 40m\n", ""), repo)
    assert len(err.findings) == 3


# --- intake ----------------------------------------------------------------------

def make_intake(tmp_path, repo):
    git = Git(SubprocessExec(), env=_git_env(tmp_path), timeout=60.0)
    journal = Journal(tmp_path / "state", clock=clock)
    return Intake(repo=repo, git=git, journal=journal, fs=LocalFilesystem()), git, journal


async def seeded(tmp_path, repo):
    intake, git, journal = make_intake(tmp_path, repo)
    await git.init(repo)
    await git.add(repo, [PLAN_FILE, "squatch/existing.py", "specs/review.md"])
    await git.commit(repo, "seed")
    return intake, git, journal


def author(repo: Path, stem: str, text: str) -> Path:
    path = repo / "tickets" / stem / "ticket.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


async def test_valid_ticket_validates_and_commits(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    path = author(repo, "widget-parser", GOOD)

    result = await intake.run()

    (c,) = result.committed
    assert result.refused == ()
    assert (c.stem, c.source, c.state) == ("widget-parser", "human", "confirmed")
    assert c.sha == await git.rev_parse(repo, "HEAD")
    assert await git.status(repo) == []
    meta, _ = parse_frontmatter(path.read_text())
    assert (meta["source"], meta["state"]) == ("human", "confirmed")
    assert meta["priority"] == "P1", "stamping leaves the authored fields alone"
    (event,) = [e for e in journal.read() if e.type == "signal"]
    assert event.ticket == "widget-parser"
    assert event.body == {"kind": "ticket_intake", "source": "human", "state": "confirmed",
                          "commit": c.sha, "path": "tickets/widget-parser/ticket.md"}


async def test_intake_commit_is_the_ticket_plane_lane(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", GOOD)
    (repo / "squatch" / "debris.py").write_text("")  # code-lane bytes never ride intake
    (repo / "squatch" / "staged.py").write_text("")
    await git.add(repo, ["squatch/staged.py"])  # operator pre-staged: stays staged, never commits

    await intake.run()

    assert await git.diff_names(repo, "HEAD~1", "HEAD") == ["tickets/widget-parser/ticket.md"]
    assert [(e.code, e.path) for e in await git.status(repo)] == [
        ("A ", "squatch/staged.py"), ("??", "squatch/debris.py")]


@pytest.mark.parametrize("text", [
    GOOD.split("---\n", 2)[2],                              # no fences at all
    "---\npriority: P1\n" + GOOD.split("---\n", 2)[2],     # opening fence, no close
    GOOD.replace("priority: P1", "priority: [P1]"),         # unhashable vocab value
    GOOD.replace("priority: P1", "state: [x]\npriority: P1"),
])
async def test_hand_authored_shape_is_refused_at_the_front_door_not_crashed(tmp_path, repo, text):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", text)
    head = await git.rev_parse(repo, "HEAD")

    result = await intake.run()

    assert result.committed == ()
    (r,) = result.refused
    assert r.stem == "widget-parser" and r.findings
    assert all(f.code == CODE and f.paved_road.strip() for f in r.findings)
    assert await git.rev_parse(repo, "HEAD") == head
    assert list(journal.read()) == []


async def test_bad_schema_ticket_is_refused_with_a_paved_road_and_left_uncommitted(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", with_frontmatter(GOOD, "tags: [x]"))
    head = await git.rev_parse(repo, "HEAD")

    result = await intake.run()

    assert result.committed == ()
    (r,) = result.refused
    assert r.stem == "widget-parser"
    assert all(f.paved_road for f in r.findings) and "tags" in r.findings[0].message
    assert await git.rev_parse(repo, "HEAD") == head
    assert [e.path for e in await git.status(repo)] == ["tickets/"]
    assert list(journal.read()) == []


def test_drain_holds_a_committed_bad_schema_ticket_without_dispatch(tmp_path, repo):
    _, git, _ = asyncio.run(seeded(tmp_path, repo))
    bad = GOOD.replace("priority: P1", "priority: P9").replace(
        "## Verification\n```\nuv run pytest tests/test_widget.py\n```\n\n", "")
    author(repo, "widget-parser", bad)
    config = repo / "config.yaml"
    config.write_text("schema_version: 1\nstate_dir: .state\nproviders: []\nrouting: []\n")
    asyncio.run(git.add(repo, ["config.yaml", "tickets/widget-parser/ticket.md"]))
    asyncio.run(git.commit(repo, "plant committed bad-schema ticket"))
    lint_error = refusal(bad, repo)
    finding = lint_error.findings[0]
    out = StringIO()

    assert main(["drain"], cwd=repo, env=_git_env(tmp_path), out=out) == 0

    line = next(line for line in out.getvalue().splitlines()
                if line.startswith("held: widget-parser "))
    assert finding.code == CODE
    assert finding.message in line
    assert finding.paved_road in line
    assert not [event for event in read_events(repo / ".state")
                if event.type == "state_transition" and event.ticket == "widget-parser"]


async def test_plan_file_in_context_is_refused_naming_the_plan_contract_road(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", with_section(GOOD, "Context", f"- {PLAN_FILE}"))
    (r,) = (await intake.run()).refused
    (f,) = r.findings
    assert PLAN_FILE in f.message and "Plan contract" in f.paved_road


async def test_unresolvable_plan_section_is_refused(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", with_section(GOOD, "Plan contract", "- section 99"))
    (r,) = (await intake.run()).refused
    assert "99" in r.findings[0].message


async def test_new_stem_claiming_a_machine_source_is_refused(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", with_frontmatter(GOOD, "source: seed"))
    (r,) = (await intake.run()).refused
    assert "seed" in r.findings[0].message and "machine" in r.findings[0].paved_road


async def test_established_seed_keeps_its_source_across_a_correction(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    path = author(repo, "widget-parser", with_frontmatter(GOOD, "source: seed\nstate: confirmed"))
    await intake.commit("widget-parser")  # the machine's own seeding path
    assert [e.body["source"] for e in journal.read() if e.type == "signal"] == ["seed"]

    path.write_text(path.read_text().replace("- stuck: 40m", "- stuck: 50m")
                    .replace("source: seed\n", ""))
    (c,) = (await intake.run()).committed

    assert c.source == "seed"
    assert parse_frontmatter(path.read_text())[0]["source"] == "seed"


async def test_intake_refuses_a_state_it_does_not_own(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", with_frontmatter(GOOD, "state: merged"))
    (r,) = (await intake.run()).refused
    assert "merged" in r.findings[0].message


async def test_pending_set_resolves_its_own_stems_and_refuses_cycles(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "aaa-core", with_section(GOOD, "Depends on", "- bbb-leaf"))
    author(repo, "bbb-leaf", with_section(GOOD, "Depends on", "- aaa-core"))
    author(repo, "ccc-solo", GOOD)

    result = await intake.run()

    assert [c.stem for c in result.committed] == ["ccc-solo"]
    assert sorted(r.stem for r in result.refused) == ["aaa-core", "bbb-leaf"]
    assert "cycle" in result.refused[0].findings[0].message


async def test_pending_set_chains_and_commits_in_dependency_order(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "bbb-leaf", with_section(GOOD, "Depends on", "- aaa-core"))
    author(repo, "aaa-core", GOOD)

    result = await intake.run()

    assert [c.stem for c in result.committed] == ["aaa-core", "bbb-leaf"]
    assert await git.status(repo) == []


async def test_clean_tree_intakes_nothing(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "widget-parser", GOOD)
    await intake.run()
    result = await intake.run()
    assert result.committed == () and result.refused == ()
    assert len([e for e in journal.read() if e.type == "signal"]) == 1


async def test_reserved_sibling_dirs_are_not_stems(tmp_path, repo):
    intake, git, journal = await seeded(tmp_path, repo)
    author(repo, "decisions", GOOD)
    (r,) = (await intake.run()).refused
    assert "decisions" in r.findings[0].message
