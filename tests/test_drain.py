"""drain.py: the ready queue to quiescence (SQUATCH_PLAN.md sections 9, 11,
18; section 19, Phase 1).

Every test drives `python -m squatch drain` in-process against a temp
checkout -- a real git repo with committed tickets and the journal under it
-- through a scripted stage-dispatch factory over the lock-held journal,
because the claims are about ORDER (depends, priority, age), what reaches
dispatch and what never does, the journal's retry accounting, and the exit
codes. The fake settles `ok` exactly as the admission does: it journals the
`to: merged` transition.
"""

import subprocess
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

from test_cli import (  # noqa: F401 -- `checkout` is a fixture
    GOOD,
    STATE,
    T0,
    author,
    checkout,
    git_env,
    transitions,
)

from squatch.__main__ import main
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.lockfile import Lockfile
from squatch.runner import EXIT_OK, EXIT_REFUSED, EXIT_TICKET
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.tickets import INTAKE_SIGNAL, Intake, stamp


class FakeClock:
    def __init__(self, now: datetime = T0):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


class Scripted:
    """Per-stem scripted outcomes behind the factory seam. `ok` journals the
    `to: merged` transition the real admission writes; `on_run` is the
    mid-run hook a test uses to move the clock or commit a ticket."""

    def __init__(self, outcomes: dict[str, list[str]], on_run=None):
        self._outcomes = {stem: list(o) for stem, o in outcomes.items()}
        self._on_run = on_run
        self.calls: list[tuple[str, int]] = []
        self.journal: Journal | None = None

    def __call__(self, journal: Journal):
        self.journal = journal
        return self

    async def run(self, ticket, *, run_seq: int) -> str:
        self.calls.append((ticket.stem, run_seq))
        if self._on_run is not None:
            await self._on_run(ticket.stem, run_seq, self.journal)
        outcome = self._outcomes[ticket.stem].pop(0)
        if outcome == "ok":
            self.journal.append("state_transition", {"to": "merged", "run_seq": run_seq},
                                ticket=ticket.stem)
        return outcome


def drain(checkout: Path, fake: Scripted | None = None, *, clock=None) -> tuple[int, str]:
    out = StringIO()
    rc = main(["drain"], cwd=checkout, env=git_env(checkout.parent), out=out,
              pipeline=fake, clock=clock or FakeClock())
    return rc, out.getvalue()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], env=git_env(repo.parent),
                          capture_output=True, text=True, check=True).stdout


def committed(repo: Path, stem: str, *, depends: str = "none", priority: str = "P1",
              stuck: int = 40, signal_at: datetime | None = None) -> Path:
    """A ticket already on the committed plane (intake ran in some earlier
    invocation): stamped, committed by hand, its intake signal planted at
    `signal_at` when given -- distinct per-stem clocks are what discriminate
    the age term."""
    text = GOOD.replace("priority: P1", f"priority: {priority}").replace(
        "- stuck: 40m", f"- stuck: {stuck}m")
    path = author(repo, stem, stamp(text, source="human", state="confirmed"), depends=depends)
    rel = f"tickets/{stem}/ticket.md"
    git(repo, "add", "--", rel)
    git(repo, "commit", "-q", "-m", f"squatch({stem}): ticket", "--", rel)
    if signal_at is not None:
        with Journal(repo / STATE, clock=lambda: signal_at) as journal:
            journal.append("signal", {"kind": INTAKE_SIGNAL, "source": "human",
                                      "state": "confirmed",
                                      "commit": git(repo, "rev-parse", "HEAD").strip(),
                                      "path": rel}, ticket=stem)
    return path


def configure(repo: Path, extra: str) -> None:
    path = repo / "config.yaml"
    path.write_text(path.read_text() + extra)
    git(repo, "commit", "-q", "-am", "config")


def draws(repo: Path, stem: str) -> list[dict]:
    return [e.body for e in read_events(repo / STATE)
            if e.type == "cap_consumed" and e.ticket == stem]


def states(repo: Path, stem: str) -> list[str]:
    return [t["to"] for t in transitions(repo, stem)]


# --- order -------------------------------------------------------------------------

def test_a_depends_edge_runs_parent_first_and_the_child_in_the_same_invocation(checkout):
    author(checkout, "child", depends="parent")
    author(checkout, "parent")
    fake = Scripted({"parent": ["ok"], "child": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("parent", 0), ("child", 0)]
    assert states(checkout, "parent") == ["running", "merged"]
    assert states(checkout, "child") == ["running", "merged"]
    assert "quiescence" in out and "2 merged this drain (parent, child)" in out


def test_equal_priority_dispatches_older_first_and_no_authoring_event_sorts_last(checkout):
    # Stem order (aaa < mmm < zzz) disagrees with age order at every step, so
    # a name-first sort cannot pass.
    committed(checkout, "zzz-older", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "aaa-younger", signal_at=T0 - timedelta(hours=1))
    committed(checkout, "mmm-no-event")
    fake = Scripted({"zzz-older": ["ok"], "aaa-younger": ["ok"], "mmm-no-event": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert [s for s, _ in fake.calls] == ["zzz-older", "aaa-younger", "mmm-no-event"]


def test_priority_outranks_age(checkout):
    committed(checkout, "old-p2", priority="P2", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "young-p0", priority="P0", signal_at=T0 - timedelta(hours=1))
    fake = Scripted({"old-p2": ["ok"], "young-p0": ["ok"]})
    rc, _ = drain(checkout, fake)
    assert rc == EXIT_OK
    assert [s for s, _ in fake.calls] == ["young-p0", "old-p2"]


def test_no_ticket_runs_before_its_depends_merged_and_a_child_unblocked_mid_drain_runs(checkout):
    # Age says child first; the edge says parent first. The child is blocked
    # at entry, and the parent's mid-invocation merge is what admits it.
    committed(checkout, "child", depends="parent", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "parent", signal_at=T0 - timedelta(hours=1))
    fake = Scripted({"parent": ["ok"], "child": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("parent", 0), ("child", 0)]


def test_a_depends_cycle_on_the_committed_plane_is_refused_with_a_paved_road(checkout):
    committed(checkout, "aa", depends="bb")
    committed(checkout, "bb", depends="aa")
    fake = Scripted({"aa": ["ok"], "bb": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_REFUSED
    assert "refused: dependency cycle" in out and "aa -> bb -> aa" in out
    assert "paved road: break the cycle" in out
    assert fake.calls == []


# --- park and re-offer -----------------------------------------------------------------

def test_a_red_independent_first_ticket_parks_and_the_second_still_runs(checkout):
    committed(checkout, "first", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "second", signal_at=T0 - timedelta(hours=1))
    configure(checkout, "caps: {retry: 0}\n")
    fake = Scripted({"first": ["gate_failed"], "second": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, "quiescence with a parked red still exits 0"
    assert fake.calls == [("first", 0), ("second", 0)]
    assert states(checkout, "first") == ["running", "gate_failed"]
    assert states(checkout, "second") == ["running", "merged"]
    assert "parked: first ended `gate_failed`" in out
    assert "retry cap spent" in out and "engine.log" in out


def test_red_then_green_on_re_offer_merges_in_one_invocation_drawing_one_retry_unit(checkout):
    author(checkout, "base")
    author(checkout, "dependent", depends="base")
    fake = Scripted({"base": ["gate_failed", "ok"], "dependent": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("base", 0), ("base", 1), ("dependent", 0)]
    assert states(checkout, "base") == ["running", "gate_failed", "running", "merged"]
    assert states(checkout, "dependent") == ["running", "merged"]
    blob = git(checkout, "rev-parse", "HEAD:tickets/base/ticket.md").strip()
    assert draws(checkout, "base") == [{"cap": "retry", "ticket_sha": blob, "run_seq": 1}]
    assert draws(checkout, "dependent") == []
    assert "re-offer: base after `gate_failed`; retry unit 1 of 6 drawn" in out


def test_eligible_work_runs_ahead_of_re_offers(checkout):
    committed(checkout, "red", signal_at=T0 - timedelta(hours=3))
    committed(checkout, "green-a", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "green-b", signal_at=T0 - timedelta(hours=1))
    fake = Scripted({"red": ["gate_failed", "ok"], "green-a": ["ok"], "green-b": ["ok"]})
    rc, _ = drain(checkout, fake)
    assert rc == EXIT_OK
    assert fake.calls == [("red", 0), ("green-a", 0), ("green-b", 0), ("red", 1)]


def test_a_stem_whose_retry_cap_is_spent_stays_parked_and_is_never_re_offered(checkout):
    author(checkout, "base")
    configure(checkout, "caps: {retry: 1}\n")
    fake = Scripted({"base": ["gate_failed", "gate_failed", "ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK
    assert fake.calls == [("base", 0), ("base", 1)], "one unit, one re-offer, then parked"
    assert len(draws(checkout, "base")) == 1
    assert "parked: base ended `gate_failed`" in out
    assert "retry cap spent (1 of 1 drawn)" in out and "never re-dispatches" in out
    # The next invocation re-derives the same spent budget: nothing dispatches.
    again = Scripted({"base": ["ok"]})
    rc, out = drain(checkout, again)
    assert rc == EXIT_OK
    assert again.calls == [] and "retry cap spent" in out


def test_a_stem_whose_infra_cap_is_spent_stays_parked_and_is_never_re_offered(checkout):
    author(checkout, "base")
    configure(checkout, "caps: {infra: 1}\n")
    fake = Scripted({"base": ["infra_error", "ok"]})

    rc, out = drain(checkout, fake)

    assert rc == EXIT_OK
    assert fake.calls == [("base", 0)]
    assert [d["cap"] for d in draws(checkout, "base")] == ["infra"]
    assert "parked: base ended `infra_error`" in out
    assert "infra cap spent (1 of 1 drawn)" in out


def test_a_retry_unit_drawn_in_one_invocation_is_spent_in_the_next_counting_retry_named_draws(checkout):
    author(checkout, "base")
    configure(checkout, "caps: {retry: 1}\n")
    first = Scripted({"base": ["gate_failed", "gate_failed"]})
    assert drain(checkout, first)[0] == EXIT_OK
    assert first.calls == [("base", 0), ("base", 1)]
    # The operator raises the cap between invocations; a draw against ANOTHER
    # cap lands in the journal too. Budget = 2 - the ONE retry-named draw:
    # exactly one re-offer (a fold over every cap would leave zero; a counter
    # forgotten across invocations would leave two).
    configure(checkout, "caps: {retry: 2}\n".replace("caps", "# raised\ncaps"))
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("cap_consumed", {"cap": "infra", "ticket_sha": "x", "run_seq": 2},
                       ticket="base")
    second = Scripted({"base": ["gate_failed", "ok"]})
    rc, out = drain(checkout, second)
    assert rc == EXIT_OK, out
    assert second.calls == [("base", 2)]
    assert [d["cap"] for d in draws(checkout, "base")] == ["retry", "infra", "retry"]
    assert "retry cap spent (2 of 2 drawn)" in out


# --- true quiescence: the tickets dir re-scan -----------------------------------------------

def test_a_ticket_committed_during_the_invocation_runs_in_the_same_invocation(checkout):
    author(checkout, "seeder")
    git_ = Git(SubprocessExec(), env=git_env(checkout.parent), timeout=60.0)

    async def seed(stem, run_seq, journal):
        if stem != "seeder":
            return
        # A seeding ticket's output: a new `confirmed` stem committed through
        # the ticket-plane lane by the machine, mid-run.
        author(checkout, "seeded", GOOD.replace("## Goal", "## Plan contract\n- section 13\n\n## Goal"))
        await Intake(repo=checkout, git=git_, journal=journal, fs=LocalFilesystem()).commit(
            "seeded", source="seed", state="confirmed")

    fake = Scripted({"seeder": ["ok"], "seeded": ["ok"]}, on_run=seed)
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("seeder", 0), ("seeded", 0)]
    assert states(checkout, "seeded") == ["running", "merged"]
    assert "2 merged this drain (seeder, seeded)" in out


def test_a_ticket_hand_authored_but_uncommitted_mid_drain_waits_for_the_next_intake(checkout):
    author(checkout, "base")

    async def scribble(stem, run_seq, journal):
        author(checkout, "half-written")

    fake = Scripted({"base": ["ok"], "half-written": ["ok"]}, on_run=scribble)
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("base", 0)]
    assert "pending intake: half-written" in out


# --- the safety envelope ---------------------------------------------------------------------

def test_the_runtime_ceiling_stops_the_next_dispatch_not_the_in_flight_stage(checkout):
    committed(checkout, "first", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "second", signal_at=T0 - timedelta(hours=1))
    clock = FakeClock()

    async def slow(stem, run_seq, journal):
        clock.advance(hours=13)  # past the shipped 12h ceiling, mid-stage

    fake = Scripted({"first": ["ok"], "second": ["ok"]}, on_run=slow)
    rc, out = drain(checkout, fake, clock=clock)
    assert rc == EXIT_TICKET, "a ceiling halt is a non-quiescent stop"
    assert fake.calls == [("first", 0)]
    assert states(checkout, "first") == ["running", "merged"], "the in-flight stage finished"
    assert states(checkout, "second") == []
    assert "halted: drain.max_runtime_hours 12 elapsed; second was next" in out
    assert "not quiescence" in out and "quiescence:" not in out
    assert "continue: `squatch drain`" in out
    timers = [(e.type, e.body["kind"]) for e in read_events(checkout / STATE)
              if e.type in ("timer_armed", "timer_fired")]
    assert timers == [("timer_armed", "drain_max_runtime"), ("timer_fired", "drain_max_runtime")]


def test_a_stuck_budget_over_max_ticket_minutes_is_held_at_dispatch_and_never_runs(checkout):
    committed(checkout, "too-long", stuck=120)
    committed(checkout, "fits", stuck=90)
    fake = Scripted({"too-long": ["ok"], "fits": ["ok"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("fits", 0)]
    assert states(checkout, "too-long") == []
    assert ("held: too-long `## Time budget` stuck 120m exceeds drain.max_ticket_minutes 90 "
            "-- lower the stuck budget in tickets/too-long/ticket.md to 90m or under") in out


# --- exit codes and refusals -----------------------------------------------------------------

def test_an_empty_queue_reports_and_exits_zero(checkout):
    fake = Scripted({})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK
    assert "quiescence: nothing eligible" in out and "0 merged this drain" in out
    assert fake.calls == []


def test_drain_is_refused_when_the_lockfile_is_held(checkout):
    author(checkout, "base")
    fake = Scripted({"base": ["ok"]})
    holder = Lockfile(checkout / STATE, instance_id="other-daemon", clock=FakeClock())
    holder.acquire()
    try:
        rc, out = drain(checkout, fake)
    finally:
        holder.release()
    assert rc == EXIT_REFUSED and "other-daemon" in out
    assert fake.calls == []


def test_a_merged_stem_and_a_rejected_stem_never_dispatch(checkout):
    committed(checkout, "done")
    committed(checkout, "killed")
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="done")
        journal.append("state_transition", {"to": "merged", "run_seq": 0}, ticket="done")
        journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="killed")
        journal.append("state_transition", {"to": "rejected", "run_seq": 0}, ticket="killed")
    fake = Scripted({"done": ["ok"], "killed": ["ok"]})
    rc, _ = drain(checkout, fake)
    assert rc == EXIT_OK and fake.calls == []


def test_an_abandoned_stem_is_eligible_without_a_retry_draw(checkout):
    committed(checkout, "reaped")
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="reaped")
        journal.append("state_transition", {"to": "abandoned", "run_seq": 0}, ticket="reaped")
    fake = Scripted({"reaped": ["ok"]})
    rc, _ = drain(checkout, fake)
    assert rc == EXIT_OK and fake.calls == [("reaped", 1)]
    assert draws(checkout, "reaped") == []


def test_drain_is_a_cli_verb(checkout):
    import sys
    proc = subprocess.run([sys.executable, "-m", "squatch", "drain"], cwd=checkout,
                          capture_output=True, text=True, env=git_env(checkout.parent))
    assert proc.returncode == EXIT_OK, proc.stderr
    assert "quiescence" in proc.stdout
