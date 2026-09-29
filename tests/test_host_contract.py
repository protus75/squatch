"""The published host contract stays copyable and bounded."""

import re
from pathlib import Path

import yaml

from squatch.config import parse


CONTRACT = Path(__file__).parents[1] / "docs" / "host-contract.md"


def _text() -> str:
    return CONTRACT.read_text()


def _config_example(text: str) -> dict:
    match = re.search(
        r"<!-- host-config-example:start -->\n```yaml\n(.*?)```\n"
        r"<!-- host-config-example:end -->",
        text,
        re.DOTALL,
    )
    assert match, "the contract must keep one delimited copyable YAML example"
    return yaml.safe_load(match.group(1))


def test_documented_schema_example_is_copyable_and_valid():
    example = _config_example(_text())

    config = parse(example, source="docs/host-contract.md")

    assert config.schema_version == 1
    assert config.review.mechanical[0].code == "test"
    assert config.merge.safety_checks == ["test"]
    assert config.report_inbox == Path(".squatch/report-inbox")


def test_contract_names_the_injected_engine_seams_and_secret_boundary():
    text = _text()

    for required in (
        "zero-argument aware-datetime callable",
        "injected sleep",
        "ProcessExec.run(argv, cwd, env,\ntimeout)",
        "never a shell",
        "Filesystem",
        "atomic",
        "refuses to\noverwrite an existing path",
        "Notifications.notify(argv)",
        "environment-variable\nname",
    ):
        assert required in text


def test_contract_bounds_report_inbox_and_preserves_bug_evidence():
    text = _text()

    for required in (
        "version-1 report files",
        "metadata first",
        "1 MiB replay file",
        "64 KiB log excerpt",
        "durable Suggestion Box custody",
        "sequential triage",
        "`bug`",
        "`## Regression`",
    ):
        assert required in text


def test_contract_preserves_managed_file_ownership_and_generated_marker_format():
    text = _text()

    assert "preserves every\nproject-owned byte outside that block" in text
    assert "malformed, partial, duplicate, or\nstray marker-like text is refused" in text
    assert "<!-- squatch:core begin version=<N> sha256=<64 hex> -->" in text
    assert "<!-- squatch:core end -->" in text
    assert "must never hand-write the marker" in text
    assert "byte-idempotent" in text


def test_contract_covers_migration_cutover_and_foreign_state_exclusion():
    text = _text()

    for required in (
        "`schema_version: 0` is the only supported predecessor",
        "`squatch migrate-config`",
        "`config.yaml.bak`",
        "operator has recorded a GO baseline",
        "`squatch serve`",
        "does not authorize foreign process-state adoption",
        "never\nadopts, reconstructs, or mutates another orchestrator's running process\nstate",
    ):
        assert required in text
