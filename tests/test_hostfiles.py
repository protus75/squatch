"""Managed ownership is byte-preserving, fail-closed, and pure."""

import ast
import hashlib
import inspect
from pathlib import Path
from typing import get_args

import pytest

from squatch import hostfiles
from squatch.config import parse
from squatch.gates import CoreDrift
from squatch.hostfiles import DriftState, ManagedBlockRefusal, classify, managed_block, render


def core_config():
    return parse({
        "schema_version": 1, "state_dir": ".squatch/state",
        "providers": [{"name": "claude", "kind": "cli",
                       "models_by_tier": {tier: "model" for tier in
                                          ("low", "medium", "high", "max")},
                       "limits": {"concurrency": 1}}],
        "routing": [{"tier": "medium", "surface": "review",
                     "candidates": [{"provider": "claude"}]}],
    }, source="test")


def branch_template(workspace: Path, core: str) -> None:
    path = workspace / "squatch" / "hostfiles.py"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"CORE = {core!r}\n")


@pytest.mark.parametrize("project", ["", "no trailing newline", "# Host\r\n\r\n café\t\r\n", "\ufeffheader\n"])
def test_first_adoption_preserves_every_project_byte(project):
    rendered = render(project, "Engine conduct")
    assert rendered == managed_block("Engine conduct") + "\n" + project
    assert rendered.count("squatch:core begin") == 1
    assert rendered.count("squatch:core end") == 1
    assert rendered.encode().endswith(project.encode())


def test_stamp_is_versioned_and_hashes_the_generated_body():
    digest = hashlib.sha256(b"Engine conduct\n").hexdigest()
    assert managed_block("Engine conduct") == (
        f"<!-- squatch:core begin version=1 sha256={digest} -->\n"
        "Engine conduct\n<!-- squatch:core end -->")


@pytest.mark.parametrize("core", ["Engine conduct", "First rule\nSecond rule\n", hostfiles.CORE])
def test_render_is_idempotent_with_multiline_core_and_surrounding_project_text(core):
    for original in ("", "# Project\r\nkeep me", "prefix\n" + managed_block("Old") + "\n\nsuffix\r\n"):
        once = render(original, core)
        assert render(once, core) == once
    result = render("prefix\n" + managed_block("Old") + "\n\nsuffix\r\n", core)
    assert result == "prefix\n" + managed_block(core) + "\n\nsuffix\r\n"


MALFORMED_MARKERS = [
    "squatch:core", "SQUATCH:CORE", "<!-- squatch:core begin -->\n",
    "<!-- squatch:core end -->", "<!-- squatch:core start -->",
    managed_block("old").split("\n", 1)[0] + "\nunterminated",
    "<!-- squatch:core end -->\n" + managed_block("old"),
    managed_block("old") + "\n" + managed_block("old"),
    managed_block("old") + "\n<!-- squatch:core end -->",
    managed_block("old") + "\nstray SQUATCH:CORE text",
    managed_block("old").replace("version=1", "version=2"),
    managed_block("old").replace("sha256=", "hash="),
    "inline " + managed_block("old"),
    managed_block("old").replace("<!-- squatch:core end -->", "<!-- squatch:core end --> junk"),
]


@pytest.mark.parametrize("content", MALFORMED_MARKERS)
def test_malformed_partial_duplicate_and_stray_marker_text_refuses(content):
    with pytest.raises(ManagedBlockRefusal):
        render(content, "new")


@pytest.mark.parametrize("core", ["<!-- squatch:core end -->", "Rule\nSQUATCH:CORE\n"])
def test_marker_like_core_is_refused_on_the_first_render(core):
    with pytest.raises(ManagedBlockRefusal):
        render("unmarked project", core)


def test_classifier_has_exactly_the_closed_drift_states():
    assert set(get_args(DriftState)) == {"missing", "current", "drifted", "refused"}
    assert classify("project", "core") == "missing"
    current = render("project-owned remainder\r\n", "core")
    assert classify(current, "core") == "current"
    assert classify(current.replace("core\n", "changed core\n"), "core") == "drifted"
    assert classify("<!-- squatch:core begin -->\n", "core") == "refused"


@pytest.mark.parametrize("content", [
    "squatch:core", "<!-- squatch:core begin -->\n", "<!-- squatch:core end -->",
    managed_block("old").split("\n", 1)[0] + "\nunterminated",
    managed_block("old") + "\n" + managed_block("old"),
])
def test_classifier_inherits_renderer_refusal_for_marker_like_text(content):
    assert classify(content, "new") == "refused"


def test_classifier_preserves_project_owned_remainder_and_is_pure():
    project = "prefix\r\n" + managed_block("old") + "\n\nsuffix\t\r\n"
    before = project.encode()
    assert classify(project, "new") == "drifted"
    assert project.encode() == before
    current = render(project, "new")
    assert current.startswith("prefix\r\n")
    assert current.endswith("\n\nsuffix\t\r\n")
    assert classify(current, "new") == "current"


async def test_core_drift_compares_the_branch_template_and_preserves_project_remainder(tmp_path):
    project = "# Project\r\nkeep these bytes\r\n"
    branch_template(tmp_path, "old core")
    path = tmp_path / "CLAUDE.md"
    path.write_text(render(project, "old core"), newline="")
    gate = CoreDrift(core_config(), candidate_template=True)

    assert (await gate.check(object(), tmp_path)).verdict == "pass"
    branch_template(tmp_path, "new core")
    report = await gate.check(object(), tmp_path)
    assert report.verdict == "fail"
    assert report.findings[0].path == "CLAUDE.md"
    assert path.read_text(newline="").endswith(project)

    path.write_text(render(path.read_text(newline=""), "new core"), newline="")
    assert (await gate.check(object(), tmp_path)).verdict == "pass"
    assert path.read_text(newline="").endswith(project)


@pytest.mark.parametrize("content", MALFORMED_MARKERS)
async def test_core_drift_refuses_malformed_managed_markers_without_rewriting(tmp_path, content):
    branch_template(tmp_path, "new")
    path = tmp_path / "CLAUDE.md"
    path.write_text(content)
    before = path.read_bytes()

    report = await CoreDrift(core_config(), candidate_template=True).check(object(), tmp_path)

    assert report.verdict == "fail"
    assert [(finding.code, finding.path) for finding in report.findings] == [
        ("core_drift", "CLAUDE.md")]
    assert path.read_bytes() == before


def test_rendering_has_no_git_or_commit_effect():
    tree = ast.parse(inspect.getsource(hostfiles))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"hashlib", "re", "typing"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "eval", "exec", "__import__"}
                   for node in ast.walk(tree))
    assert isinstance(render("project", "core"), str)
    assert isinstance(classify("project", "core"), str)
