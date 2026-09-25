import pytest

from test_cli import GOOD, STATE, author, checkout, git_env  # noqa: F401
from test_drain import FakeClock, Scripted, drain, states
from test_stages import PLAN, PYTHON, TICKET, repo, env  # noqa: F401

from squatch.config import load
from squatch.git import Git, GitError
from squatch.journal import Event, Journal
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.seeds import SEED_LIFT_SIGNAL, Seed, authored_seeds, blob_sha, validate_batch
from squatch.tickets import Intake


def seed_text(*, depends: str = "none", source: str = "seed",
              state: str = "confirmed") -> str:
    text = TICKET.format(
        verify=f'{PYTHON} -c "import sys; sys.exit(0)"',
        frontmatter=f"source: {source}\nstate: {state}")
    return text.replace("## Depends on\n- none", f"## Depends on\n- {depends}")


def seed(stem: str, **kwargs) -> Seed:
    text = seed_text(**kwargs)
    return Seed(stem, text, blob_sha(text))


async def test_authored_seeds_are_foreign_dirty_ticket_files_only(repo, env):
    git_ = Git(SubprocessExec(), env=env, timeout=60.0)
    worktree = repo.parent / "worktree"
    await git_.worktree_add(repo, worktree, "seeder", "main")
    for stem in ("alpha-seed", "beta-seed"):
        path = worktree / "tickets" / stem / "ticket.md"
        path.parent.mkdir(parents=True)
        path.write_text(seed_text())
    own = worktree / "tickets" / "seeder" / "run.md"
    own.parent.mkdir(parents=True)
    own.write_text("run\n")

    found = await authored_seeds(worktree, "seeder", git_)

    assert [(item.stem, item.sha) for item in found] == [
        (name, blob_sha(seed_text())) for name in ("alpha-seed", "beta-seed")]
    for item in found:
        (worktree / item.path).unlink()
    assert await authored_seeds(worktree, "seeder", git_) == ()


async def test_unchanged_human_reintake_still_fails_in_the_shared_lane(repo, env):
    git_ = Git(SubprocessExec(), env=env, timeout=60.0)
    text = seed_text(source="human")
    path = repo / "tickets" / "human-ticket" / "ticket.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    with Journal(repo / load(None, cwd=repo).state_dir, clock=FakeClock()) as journal:
        intake = Intake(repo=repo, git=git_, journal=journal, fs=LocalFilesystem())
        await intake.commit("human-ticket")
        signals = len([event for event in journal.read() if event.type == "signal"])

        with pytest.raises(GitError):
            await intake.commit("human-ticket")

        assert len([event for event in journal.read() if event.type == "signal"]) == signals


def test_validate_batch_covers_cap_schema_dependencies_cycles_and_collisions(repo, env):
    config = load(None, cwd=repo)
    four = tuple(seed(f"seed-{number}") for number in range(4))
    findings = validate_batch(
        four, repo=repo, plan=PLAN, config=config, events=(), seeder="seeder")
    assert any("over seeding.max_seeds_per_admission 3" in issue.message
               and "-continue" in issue.paved_road for issue in findings)

    findings = validate_batch(
        (seed("bad-source", source="human"), seed("bad-dependency", depends="ghost")),
        repo=repo, plan=PLAN, config=config, events=(), seeder="seeder")
    assert any("source: seed" in issue.message for issue in findings)
    assert any("does not resolve" in issue.message for issue in findings)

    findings = validate_batch(
        (seed("cycle-alpha", depends="cycle-beta"),
         seed("cycle-beta", depends="cycle-alpha")),
        repo=repo, plan=PLAN, config=config, events=(), seeder="seeder")
    assert any("dependency cycle" in issue.message for issue in findings)

    existing = repo / "tickets" / "existing-seed" / "ticket.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(seed_text())
    candidate = seed("existing-seed")
    findings = validate_batch(
        (candidate,), repo=repo, plan=PLAN, config=config, events=(), seeder="seeder")
    assert any("already exists on main" in issue.message for issue in findings)
    prior = Event(v=1, type="signal", ts="2026-09-25T12:00:00+00:00",
                  ticket="seeder", key=None,
                  body={"kind": SEED_LIFT_SIGNAL, "seeder": "seeder", "run_seq": 0,
                        "seeds": {"existing-seed": candidate.sha}})
    findings = validate_batch(
        (candidate,), repo=repo, plan=PLAN, config=config, events=(prior,), seeder="seeder")
    assert not any("already exists on main" in issue.message for issue in findings)


def test_open_lift_does_not_exempt_another_seeders_intake(repo, env):
    config = load(None, cwd=repo)
    existing = repo / "tickets" / "foreign-seed" / "ticket.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(seed_text())
    candidate = seed("foreign-seed")
    intent = Event(
        v=1, type="effect_intent", ts="2026-09-25T12:00:00+00:00",
        ticket="seeder-a", key="lift/seeder-a/0/seeds", body={})
    foreign = Event(
        v=1, type="signal", ts="2026-09-25T12:00:01+00:00",
        ticket="foreign-seed", key=None,
        body={"kind": "ticket_intake", "source": "seed", "state": "confirmed",
              "commit": "foreign-commit", "path": candidate.path,
              "seeder": "seeder-b"})

    findings = validate_batch(
        (candidate,), repo=repo, plan=PLAN, config=config,
        events=(intent, foreign), seeder="seeder-a")

    assert any("already exists on main" in issue.message for issue in findings)


def test_a_lifted_seed_is_dispatched_in_the_same_drain_invocation(checkout):
    author(checkout, "seeder")
    git_ = Git(SubprocessExec(), env=git_env(checkout.parent), timeout=60.0)

    async def lift(stem, run_seq, journal):
        if stem != "seeder":
            return
        text = GOOD.replace(
            "## Goal", "## Plan contract\n- section 13\n\n## Goal")
        author(checkout, "lifted-seed", text, depends="seeder")
        await Intake(repo=checkout, git=git_, journal=journal,
                     fs=LocalFilesystem()).commit(
            "lifted-seed", source="seed", state="confirmed")

    fake = Scripted({"seeder": ["ok"], "lifted-seed": ["ok"]}, on_run=lift)
    rc, output = drain(checkout, fake, clock=FakeClock())

    assert rc == 0 and fake.calls == [("seeder", 0), ("lifted-seed", 0)]
    assert states(checkout, "lifted-seed") == ["running", "merged"]
    assert "quiescence" in output and "2 merged this drain" in output
