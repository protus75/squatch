"""Allowlisted custody of a failed attempt's worktree-only material."""

from test_stages import (KEY_NAME, STEM, WIDGET, Agent, answer, env, implementer, repo, review,
                         run_record)  # noqa: F401
from test_terminal import RED, Drive, author, ticket

from squatch.harvest import HARVEST_FILE, TAIL_CHARS, Harvest


async def test_gate_failure_harvests_allowlisted_material_to_main(repo, env):
    author(repo, ticket(verify=RED))

    def leave_uncommitted_source_change(req):
        implementer(env, WIDGET)(req)
        (req.worktree / WIDGET[0]).write_text(WIDGET[1] + "PRIVATE_DIFF_LINE = 2\n")
        (req.worktree / "squatch" / "untracked.py").write_text("PRIVATE_NEW_LINE = 3\n")

    drive = Drive(repo, env, Agent(answer("implemented"),
                                   actions=[leave_uncommitted_source_change]))

    await drive.run()

    attempt = repo / "tickets" / STEM / "attempts" / "0"
    artifact = Harvest.model_validate_json((attempt / HARVEST_FILE).read_text())
    assert artifact.outcome == "gate_failed" and artifact.stage == "check"
    assert artifact.run_seq == 0 and artifact.findings
    assert "squatch/widget.py" in artifact.diff_stat
    assert "squatch/untracked.py" in artifact.diff_stat
    assert (attempt / "run.md").is_file()
    spool = drive.state / "spools" / STEM / "0"
    assert set(artifact.spool_tails) == {
        path.relative_to(spool).as_posix() for path in spool.rglob("*") if path.is_file()}
    assert all(len(tail) <= TAIL_CHARS for tail in artifact.spool_tails.values())
    harvested = (attempt / HARVEST_FILE).read_text() + (attempt / "run.md").read_text()
    assert "WIDGET = 1" not in harvested and "PRIVATE_DIFF_LINE = 2" not in harvested
    assert "PRIVATE_NEW_LINE = 3" not in harvested
    assert f"tickets/{STEM}/attempts/0/{HARVEST_FILE}" in drive.main_files()
    assert f"tickets/{STEM}/attempts/0/run.md" in drive.main_files()


async def test_review_prompt_tail_elides_the_unreviewed_diff(repo, env):
    author(repo, ticket())
    private = "UNREVIEWED_SOURCE_CONTENT = 'must stay on the branch'\n"
    drive = Drive(
        repo, env,
        Agent(answer("implemented"), review("snag", {"message": "wrong"}),
              actions=[implementer(env, (WIDGET[0], private)), None]))

    await drive.run()

    attempt = repo / "tickets" / STEM / "attempts" / "0"
    artifact = Harvest.model_validate_json((attempt / HARVEST_FILE).read_text())
    prompt = artifact.spool_tails["001-prompt.md"]
    marker = "<<<" + "squatch:"
    assert f'{marker}data name="diff"' in prompt
    assert "(diff elided:" in prompt
    assert private.strip() not in "".join(
        path.read_text(errors="replace") for path in attempt.rglob("*") if path.is_file())


async def test_harvest_files_each_second_problem_and_records_the_ids(repo, env):
    author(repo, ticket(verify=RED))
    record = run_record().replace(
        "## Second problems filed\n\n",
        "## Second problems filed\n- first adjacent problem\n- second adjacent problem\n\n")
    drive = Drive(repo, env, Agent(answer("implemented"),
                                   actions=[implementer(env, WIDGET, record=record)]))

    await drive.run()

    artifact = Harvest.model_validate_json(
        (repo / "tickets" / STEM / "attempts" / "0" / HARVEST_FILE).read_text())
    assert len(artifact.filed) == 2
    messages = [drive.state / "box" / f"{id.removeprefix('box-')}.json"
                for id in artifact.filed]
    assert all(path.is_file() for path in messages)
    records = [__import__("json").loads(path.read_text()) for path in messages]
    assert all(r["status"] == "pending" and r["message_class"] == "suggestion"
               and r["origin"] == STEM for r in records)


async def test_harvest_with_no_second_problems_records_an_empty_list(repo, env):
    author(repo, ticket(verify=RED))
    drive = Drive(repo, env, Agent(answer("implemented"),
                                   actions=[implementer(env, WIDGET)]))
    await drive.run()
    artifact = Harvest.model_validate_json(
        (repo / "tickets" / STEM / "attempts" / "0" / HARVEST_FILE).read_text())
    assert artifact.filed == ()


async def test_harvest_redacts_second_problems_before_box_custody(repo, env):
    secret = "box-must-not-capture-this-secret"
    token = f"[REDACTED:{KEY_NAME}]"
    author(repo, ticket(verify=RED))
    record = run_record().replace(
        "## Second problems filed\n\n",
        f"## Second problems filed\n- leaked credential {secret}\n\n")
    drive = Drive(repo, {**env, KEY_NAME: secret}, Agent(
        answer("implemented"), actions=[implementer(env, WIDGET, record=record)]))

    await drive.run()

    captured = "".join(path.read_text() for path in (drive.state / "box").glob("*.json"))
    assert token in captured and secret not in captured
