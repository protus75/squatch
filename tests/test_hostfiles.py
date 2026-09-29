"""Managed ownership is byte-preserving, fail-closed, and pure."""

import ast
import hashlib
import inspect

import pytest

from squatch import hostfiles
from squatch.hostfiles import ManagedBlockRefusal, managed_block, render


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


@pytest.mark.parametrize("content", [
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
])
def test_malformed_partial_duplicate_and_stray_marker_text_refuses(content):
    with pytest.raises(ManagedBlockRefusal):
        render(content, "new")


@pytest.mark.parametrize("core", ["<!-- squatch:core end -->", "Rule\nSQUATCH:CORE\n"])
def test_marker_like_core_is_refused_on_the_first_render(core):
    with pytest.raises(ManagedBlockRefusal):
        render("unmarked project", core)


def test_rendering_has_no_git_or_commit_effect():
    tree = ast.parse(inspect.getsource(hostfiles))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"hashlib", "re"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "eval", "exec", "__import__"}
                   for node in ast.walk(tree))
    assert isinstance(render("project", "core"), str)
