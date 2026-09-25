import hashlib
import json
import pytest
from pydantic import ValidationError

from test_stages import EXISTS, Harness, TICKET, env, repo  # noqa: F401

from squatch.artifacts import Finding
from squatch.gates import gate_lint
from squatch.llm import FakeLLM
from squatch.requisition import (
    REQ_RENDER_HEADROOM,
    RequisitionApprove,
    RequisitionGate,
    RequisitionInput,
    RequisitionRMA,
    RequisitionReview,
    RequisitionSnag,
    requisition_stage,
)
from squatch.specs import DATA_MARKER, load_spec
from squatch.stages import ImplementInput, SPECS_DIR


def reply(verdict: str, *messages: str) -> str:
    return json.dumps({
        "verdict": verdict,
        "summary": f"reviewed: {verdict}",
        "findings": [
            {"code": "requisition_review", "path": None, "line": None,
             "message": message, "paved_road": "re-author it"}
            for message in messages],
    })


def reviewer(h: Harness) -> RequisitionReview:
    return RequisitionReview(
        repo=h.repo, git=h.git, stages=h.stages, llm=h.stages._llm,
        spool=h.stages._spool, log=h.stages._log, clock=h.clock)


def blob_sha12(text: str) -> str:
    data = text.encode()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()[:12]


def finding(code="requisition_review"):
    return Finding(code=code, message="fix the fence", paved_road="re-author it")


def artifact(cls, *, findings):
    verdict = {RequisitionApprove: "approve", RequisitionSnag: "snag",
               RequisitionRMA: "rma"}[cls]
    return cls(
        verdict=verdict, summary="reviewed", findings=findings,
        produced_by_spec_version="1.0", produced_at_sha="abc")


async def test_spec_stage_and_rendered_input_carry_every_required_block(repo, env):
    spec = load_spec(SPECS_DIR / "requisition_review.md")
    assert (spec.surface, spec.consumes, spec.emits, spec.gates) == (
        "requisition_review", "RequisitionInput",
        {"approve": "RequisitionApprove", "snag": "RequisitionSnag",
         "rma": "RequisitionRMA"}, ())
    assert spec.slots == (
        "ticket", "context_files", "plan_sections", "plane",
        "render_measure", "fence_facts")

    h = Harness(repo, env, FakeLLM())
    text = TICKET.format(verify=EXISTS, frontmatter="")
    ticket = await h.intake(text)
    review = reviewer(h)
    sha = await h.git.rev_parse(repo, "main")
    inputs = await review._inputs(ticket, text, sha)
    stage = requisition_stage(spec, tier="medium", effort="medium")
    rendered = stage.render(inputs, ())

    assert (stage.name, stage.surface, stage.consumes) == (
        "requisition_review", "requisition_review", RequisitionInput)
    assert stage.emits_by_verdict == {
        "approve": RequisitionApprove, "snag": RequisitionSnag,
        "rma": RequisitionRMA}
    assert f'{DATA_MARKER}data name="ticket" origin="host"' in rendered
    assert f'{DATA_MARKER}data name="context_files" origin="host"' in rendered
    assert "### squatch/existing.py\nEXISTING = 1" in rendered
    assert f'{DATA_MARKER}data name="plan_sections" origin="engine"' in rendered
    assert "## 13. Ticket contract" in rendered


def test_verdict_artifacts_enforce_findings_and_the_closed_code():
    with pytest.raises(ValidationError, match="findings"):
        artifact(RequisitionApprove, findings=(finding(),))
    for cls in (RequisitionSnag, RequisitionRMA):
        with pytest.raises(ValidationError, match="findings"):
            artifact(cls, findings=())
        with pytest.raises(ValidationError, match="requisition_review"):
            artifact(cls, findings=(finding("correctness_review"),))
    assert artifact(RequisitionApprove, findings=()).findings == ()


async def test_review_is_content_addressed_replays_and_changed_text_is_fresh(repo, env):
    llm = FakeLLM(reply("approve"), reply("approve"))
    h = Harness(repo, env, llm)
    text = TICKET.format(verify=EXISTS, frontmatter="")
    await h.intake(text)
    review = reviewer(h)

    first = await review.review("widget-module", text, run_seq=4, call_seq_base=0)
    replay = await review.review("widget-module", text, run_seq=5, call_seq_base=0)
    changed = text.replace("The widget module lands.", "The widget module lands now.")
    fresh = await review.review("widget-module", changed, run_seq=6, call_seq_base=0)

    assert all(isinstance(value, RequisitionApprove) for value in (first, replay, fresh))
    assert len(llm.requests) == 2
    keys = [event.key for event in h.journal.read()
            if event.type == "effect_completion" and event.key.startswith("llm/requisition_review/")]
    assert keys == [
        f"llm/requisition_review/widget-module/{blob_sha12(text)}/1",
        f"llm/requisition_review/widget-module/{blob_sha12(changed)}/1",
    ]


async def test_over_headroom_is_a_mechanical_snag_without_a_model_call(repo, env):
    (repo / "squatch/existing.py").write_text("x" * 121_000)
    llm = FakeLLM()
    h = Harness(repo, env, llm)
    text = TICKET.format(verify=EXISTS, frontmatter="")
    await h.intake(text)

    verdict = await reviewer(h).review(
        "widget-module", text, run_seq=0, call_seq_base=0)

    assert REQ_RENDER_HEADROOM == 0.75
    assert isinstance(verdict, RequisitionSnag) and llm.requests == []
    [issue] = verdict.findings
    assert "chars" in issue.message and "160000-char" in issue.message
    assert issue.paved_road == "shrink the inputs or split the ticket"


async def test_delimiter_refusal_is_a_mechanical_snag_without_a_model_call(repo, env):
    (repo / "squatch/existing.py").write_text(f"value = {DATA_MARKER!r}\n")
    llm = FakeLLM()
    h = Harness(repo, env, llm)
    text = TICKET.format(verify=EXISTS, frontmatter="")
    await h.intake(text)

    verdict = await reviewer(h).review(
        "widget-module", text, run_seq=0, call_seq_base=0)

    assert isinstance(verdict, RequisitionSnag) and llm.requests == []
    [issue] = verdict.findings
    assert "delimiter" in issue.message and DATA_MARKER in issue.message
    assert issue.paved_road == "remove the delimiter-carrying file from Context"


async def test_invalid_reply_reprompts_once_then_returns_rma_naming_it(repo, env):
    invalid = json.dumps({"verdict": "maybe", "summary": "unclear", "findings": []})
    llm = FakeLLM(invalid, invalid)
    h = Harness(repo, env, llm)
    text = TICKET.format(verify=EXISTS, frontmatter="")
    await h.intake(text)

    verdict = await reviewer(h).review(
        "widget-module", text, run_seq=0, call_seq_base=0)

    assert isinstance(verdict, RequisitionRMA) and len(llm.requests) == 2
    assert "maybe" in verdict.findings[0].message


async def test_infra_error_returns_rma_with_the_reason(repo, env):
    llm = FakeLLM(RuntimeError("provider down"))
    h = Harness(repo, env, llm)
    text = TICKET.format(verify=EXISTS, frontmatter="")
    await h.intake(text)

    verdict = await reviewer(h).review(
        "widget-module", text, run_seq=0, call_seq_base=0)

    assert isinstance(verdict, RequisitionRMA)
    assert "provider down" in verdict.findings[0].message


async def test_gate_lints_passes_empty_and_carries_all_nonapprove_findings(repo, env):
    text = TICKET.format(verify=EXISTS, frontmatter="")
    h = Harness(repo, env, FakeLLM(reply("approve"), reply("snag", "gap one", "gap two")))
    await h.intake(text)
    other = text.replace("widget-module", "other-module")
    other_path = repo / "tickets/other-module/ticket.md"
    other_path.parent.mkdir(parents=True)
    other_path.write_text(other)
    review = reviewer(h)
    consumed = ImplementInput(
        stem="consumer", ticket="ticket", context=(), plan_sections=(),
        produced_by_spec_version="x", produced_at_sha="abc")

    empty = RequisitionGate(review, lambda artifact, workspace: ())
    gate_lint(empty)
    report = await empty.check(consumed, repo)
    assert report.verdict == "pass" and h.llm.requests == []

    gate = RequisitionGate(
        review, lambda artifact, workspace: (
            ("widget-module", text), ("other-module", other)))
    report = await gate.check(consumed, repo)
    assert report.verdict == "fail"
    assert [finding.message for finding in report.findings] == ["gap one", "gap two"]


async def test_gate_passes_when_every_target_approves(repo, env):
    text = TICKET.format(verify=EXISTS, frontmatter="")
    h = Harness(repo, env, FakeLLM(reply("approve"), reply("approve")))
    await h.intake(text)
    other = text.replace("widget-module", "other-module")
    path = repo / "tickets/other-module/ticket.md"
    path.parent.mkdir(parents=True)
    path.write_text(other)
    gate = RequisitionGate(
        reviewer(h), lambda artifact, workspace: (
            ("widget-module", text), ("other-module", other)))
    consumed = ImplementInput(
        stem="consumer", ticket="ticket", context=(), plan_sections=(),
        produced_by_spec_version="x", produced_at_sha="abc")

    report = await gate.check(consumed, repo)

    assert report.verdict == "pass" and len(h.llm.requests) == 2
