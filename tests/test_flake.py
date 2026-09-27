import ast
from datetime import datetime, timezone
from pathlib import Path

from squatch.box import Box
from squatch.daemon import compose_daemon_flake
from squatch.flake import Flake, FlakeRerun, fold_quarantine
from squatch.journal import Journal, read_events
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def _report(box: Box):
    result = box.enqueue(message_class="failure_report", summary="intermittent check",
                         detail="named check failed on its first run", origin="verification")
    return box.get(result.id)


def _merged(journal: Journal, stem: str) -> None:
    journal.append("state_transition", {
        "to": "merged", "run_seq": 4, "commit": "a" * 40,
        "reviewed_sha": "b" * 40,
    }, ticket=stem)


def _release_rerun(test_id: str, fix_stem: str, *, green: bool = True) -> FlakeRerun:
    return FlakeRerun(test_id=test_id, fix_stem=fix_stem, green=green)


def test_detects_a_named_fail_then_same_workspace_no_change_pass_and_folds_ledger(tmp_path):
    workspace = tmp_path / "worktree"
    no_code_change = "same-tree"
    reruns = [("tests/test_widget.py::test_named_check", False, workspace, no_code_change),
              ("tests/test_widget.py::test_named_check", True, workspace, no_code_change)]
    test_id, first_passed, first_workspace, first_tree = reruns[0]
    _, rerun_passed, rerun_workspace, rerun_tree = reruns[1]
    assert not first_passed and rerun_passed
    assert first_workspace == rerun_workspace and first_tree == rerun_tree

    box = Box(tmp_path, fs=LocalFilesystem(), clock=lambda: NOW)
    existing_report = box.enqueue(
        message_class="failure_report", summary="existing intermittent check",
        detail="a different named check failed on its first run", origin="verification")
    report = _report(box)
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        flake = compose_daemon_flake(journal=journal, box=box)
        assert isinstance(flake, Flake)
        existing = box.get(existing_report.id)
        assert flake.detect(test_id="tests/test_widget.py::test_existing_check",
                            signature=existing.signature, box_id=existing.id)
        before = flake.quarantine()
        assert flake.detect(test_id=test_id, signature=report.signature, box_id=report.id)
        events = tuple(journal.read())
        signal = next(event for event in events if event.key == f"flake/{report.id}")
        assert (signal.key, signal.body) == (
            (f"flake/{report.id}", {"kind": "flake_detected", "test_id": test_id,
                                     "signature": report.signature, "box_id": report.id}))
        assert not [event for event in events if "release" in event.key or
                    event.body.get("kind") == "flake_released"]
        assert flake.quarantine() == {existing.id: "tests/test_widget.py::test_existing_check",
                                      report.id: test_id}
        assert flake.quarantine()[existing.id] == before[existing.id]
        assert box.get(report.id).status == "pending"


def test_flake_ledger_reconstructs_and_deduplicates_the_same_report(tmp_path):
    box = Box(tmp_path, fs=LocalFilesystem(), clock=lambda: NOW)
    report = _report(box)
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        flake = compose_daemon_flake(journal=journal, box=box)
        assert flake.detect(test_id="tests/test_widget.py::test_named_check",
                            signature=report.signature, box_id=report.id)
        assert not flake.detect(test_id="tests/test_widget.py::test_named_check",
                                signature=report.signature, box_id=report.id)
        assert len(tuple(journal.read())) == 1

    reconstructed = fold_quarantine(read_events(tmp_path))
    assert reconstructed == {report.id: "tests/test_widget.py::test_named_check"}


def test_release_binds_the_authored_fix_merged_transition_and_green_rerun(tmp_path):
    test_id, fix_stem = "tests/test_widget.py::test_named_check", "fix-widget-flake"
    box = Box(tmp_path, fs=LocalFilesystem(), clock=lambda: NOW)
    report = _report(box)
    other = box.enqueue(message_class="failure_report", summary="other intermittent check",
                        detail="a different test flakes", origin="verification")
    box.resolve(report.id, status="authored", link=fix_stem, note="authored a fix")
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        flake = compose_daemon_flake(journal=journal, box=box)
        assert flake.detect(test_id=test_id, signature=report.signature, box_id=report.id)
        assert flake.detect(test_id="tests/test_other.py::test_other", signature=box.get(other.id).signature,
                            box_id=other.id)
        _merged(journal, fix_stem)
        assert flake.release(box_id=report.id, rerun=_release_rerun(test_id, fix_stem))
        events = tuple(journal.read())
        release = next(event for event in events
                       if isinstance(event.key, str) and event.key.startswith("flake-release/"))
        assert (release.key, release.body) == (
            f"flake-release/{report.id}/{fix_stem}",
            {"kind": "flake_released", "test_id": test_id, "signature": report.signature,
             "box_id": report.id, "fix_stem": fix_stem})
        assert events.index(release) > next(i for i, event in enumerate(events)
                                            if event.key == f"flake/{report.id}")
        assert flake.quarantine() == {other.id: "tests/test_other.py::test_other"}

    assert fold_quarantine(read_events(tmp_path)) == {other.id: "tests/test_other.py::test_other"}


def test_release_refusals_preserve_the_ledger_and_events(tmp_path):
    test_id, fix_stem = "tests/test_widget.py::test_named_check", "fix-widget-flake"
    cases = (
        ("wrong status", "pending", fix_stem, True, fix_stem),
        ("link mismatch", "authored", "other-fix", True, fix_stem),
        ("unmerged stem", "authored", fix_stem, False, fix_stem),
        ("red rerun", "authored", fix_stem, True, fix_stem, False),
        ("other test rerun", "authored", fix_stem, True, fix_stem, True,
         "tests/test_other.py::test_named_check"),
        ("other fix rerun", "authored", fix_stem, True, "other-fix"),
    )
    for case in cases:
        _, status, link, merged, rerun_stem, *extra = case
        green = extra[0] if extra and isinstance(extra[0], bool) else True
        rerun_test = extra[-1] if extra and isinstance(extra[-1], str) else test_id
        state = tmp_path / case[0].replace(" ", "-")
        box = Box(state, fs=LocalFilesystem(), clock=lambda: NOW)
        report = _report(box)
        if status == "authored":
            box.resolve(report.id, status=status, link=link, note="authored a fix")
        with Journal(state, clock=lambda: NOW) as journal:
            flake = Flake(journal=journal, box=box)
            assert flake.detect(test_id=test_id, signature=report.signature, box_id=report.id)
            if merged:
                _merged(journal, fix_stem)
            before_events, before_quarantine = tuple(journal.read()), flake.quarantine()
            assert not flake.release(box_id=report.id,
                                     rerun=_release_rerun(rerun_test, rerun_stem, green=green))
            assert tuple(journal.read()) == before_events
            assert flake.quarantine() == before_quarantine


def test_release_identity_is_terminal_after_redetection_and_reconstruction(tmp_path):
    test_id, fix_stem = "tests/test_widget.py::test_named_check", "fix-widget-flake"
    box = Box(tmp_path, fs=LocalFilesystem(), clock=lambda: NOW)
    report = _report(box)
    box.resolve(report.id, status="authored", link=fix_stem, note="authored a fix")
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        flake = Flake(journal=journal, box=box)
        assert flake.detect(test_id=test_id, signature=report.signature, box_id=report.id)
        _merged(journal, fix_stem)
        rerun = _release_rerun(test_id, fix_stem)
        assert flake.release(box_id=report.id, rerun=rerun)
        assert flake.detect(test_id=test_id, signature=report.signature, box_id=report.id)
        before_events, before_quarantine = tuple(journal.read()), flake.quarantine()
        assert not flake.release(box_id=report.id, rerun=rerun)
        assert tuple(journal.read()) == before_events
        assert flake.quarantine() == before_quarantine == {report.id: test_id}

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        reconstructed = Flake(journal=journal, box=box)
        assert not reconstructed.release(box_id=report.id, rerun=_release_rerun(test_id, fix_stem))
        assert reconstructed.quarantine() == {report.id: test_id}


def test_production_roots_do_not_construct_or_call_the_dormant_hook():
    for name in ("__main__.py", "drain.py"):
        tree = ast.parse((ROOT / "squatch" / name).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert not any((isinstance(call.func, ast.Name)
                        and call.func.id == "compose_daemon_flake")
                       or (isinstance(call.func, ast.Attribute)
                           and call.func.attr == "compose_daemon_flake")
                       for call in calls)
