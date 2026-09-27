import ast
from datetime import datetime, timezone
from pathlib import Path

from squatch.box import Box
from squatch.daemon import compose_daemon_flake
from squatch.flake import Flake, fold_quarantine
from squatch.journal import Journal, read_events
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def _report(box: Box):
    result = box.enqueue(message_class="failure_report", summary="intermittent check",
                         detail="named check failed on its first run", origin="verification")
    return box.get(result.id)


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


def test_production_roots_do_not_construct_or_call_the_dormant_hook():
    for name in ("__main__.py", "drain.py"):
        tree = ast.parse((ROOT / "squatch" / name).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert not any((isinstance(call.func, ast.Name)
                        and call.func.id == "compose_daemon_flake")
                       or (isinstance(call.func, ast.Attribute)
                           and call.func.attr == "compose_daemon_flake")
                       for call in calls)
