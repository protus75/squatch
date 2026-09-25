from pathlib import Path

import pytest
from pydantic import ValidationError

from squatch.diagnose import (VERDICTS, Diagnosis, DiagnosisInput, DiagnosisRecord,
                              diagnose_stage)
from squatch.specs import load_spec

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = {"produced_by_spec_version": "test", "produced_at_sha": "abc"}


def inputs(**changes):
    values = dict(stem="widget", ticket="ticket text", harvest="harvest text",
                  run_record="run text", diff="diff text", prior_lessons=("old lesson",),
                  **PROVENANCE)
    values.update(changes)
    return DiagnosisInput(**values)


def test_diagnose_spec_and_stage_render_every_input_as_a_data_block():
    spec = load_spec(ROOT / "specs" / "diagnose.md")
    assert (spec.surface, spec.consumes, spec.emits) == ("diagnose", "DiagnosisInput", "Diagnosis")
    assert spec.slots == ("ticket", "harvest", "run_record", "diff", "prior_lessons")
    assert spec.optional == {"run_record", "diff", "prior_lessons"}

    stage = diagnose_stage(spec, tier="high", effort="medium")
    rendered = stage.render(inputs(), ())
    for name in spec.slots:
        assert f'name="{name}"' in rendered
    assert rendered.count("<<<squatch:data ") == 5

    minimal = stage.render(inputs(run_record=None, diff=None, prior_lessons=()), ())
    assert 'name="run_record"' not in minimal
    assert 'name="diff"' not in minimal
    assert 'name="prior_lessons"' not in minimal


@pytest.mark.parametrize("verdict", sorted(VERDICTS))
def test_diagnosis_accepts_each_closed_verdict(verdict):
    Diagnosis(verdict=verdict, lessons=("next step",), reason="because", **PROVENANCE)


@pytest.mark.parametrize("changes", [
    {"verdict": "shrug"},
    {"lessons": ()},
    {"lessons": ("x" * 301,)},
])
def test_diagnosis_refuses_values_outside_its_closed_shape(changes):
    values = dict(verdict="retry", lessons=("next step",), reason="because", **PROVENANCE)
    values.update(changes)
    with pytest.raises(ValidationError):
        Diagnosis(**values)


def test_diagnosis_record_refuses_a_call_outside_the_closed_set():
    with pytest.raises(ValidationError):
        DiagnosisRecord(run_seq=0, outcome="gate_failed", call="shrug", verdict=None,
                        lessons=(), reason=None, detail=None)
