import os
import subprocess

import pytest
from pydantic import ValidationError

from squatch.git import Git
from squatch.registry import Record, commit, load, write
from squatch.seams import LocalFilesystem, SubprocessExec


def record(**changes):
    values = {"id": "known-decision", "kind": "decision", "link": "ticket-one",
              "reopen_after_days": 30, "message": "box-000001-deadbeef",
              "body": "Rationale and evidence."}
    values.update(changes)
    return Record(**values)


def test_record_is_closed_and_requires_the_reopen_window():
    with pytest.raises(ValidationError):
        Record(id="known-decision", kind="decision", link="ticket-one",
               message="box-000001-deadbeef", body="body")
    with pytest.raises(ValidationError):
        record(kind="maybe")
    with pytest.raises(ValidationError):
        record(id="Bad_Name")


def test_write_and_load_round_trip_and_bad_file_is_named(tmp_path):
    expected = record()
    write(tmp_path, expected, fs=LocalFilesystem())
    assert load(tmp_path) == [expected]
    bad = tmp_path / "tickets" / "decisions" / "bad.md"
    bad.write_text("not frontmatter")
    with pytest.raises(ValueError, match="bad.md"):
        load(tmp_path)


def test_load_refuses_body_in_frontmatter_and_names_the_file(tmp_path):
    path = tmp_path / "tickets" / "decisions" / "bad-body.md"
    path.parent.mkdir(parents=True)
    path.write_text("""---
id: bad-body
kind: decision
link: ticket-one
reopen_after_days: 30
message: box-000001-deadbeef
body: hidden
---
Visible body.
""")

    with pytest.raises(ValueError, match="bad-body.md.*unknown frontmatter key 'body'"):
        load(tmp_path)


async def test_commit_is_one_pathspec_commit_on_main(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
           "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test"}
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], env=env, check=True)
    (repo / "seed").write_text("seed")
    subprocess.run(["git", "-C", str(repo), "add", "--", "seed"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], env=env,
                   check=True)
    expected = record()
    write(repo, expected, fs=LocalFilesystem())
    (repo / "unrelated").write_text("not committed")
    git = Git(SubprocessExec(), env=env, timeout=60)
    await commit(repo, expected, git=git)
    subject = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%s"], env=env,
                             capture_output=True, text=True, check=True).stdout.strip()
    names = subprocess.run(["git", "-C", str(repo), "show", "--format=", "--name-only",
                            "HEAD"], env=env, capture_output=True, text=True,
                           check=True).stdout.splitlines()
    assert subject == "squatch(decisions): known-decision"
    assert names == ["tickets/decisions/known-decision.md"]
