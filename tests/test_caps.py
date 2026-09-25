"""The single failure-spine cap vocabulary, writer, and lineage fold."""

from squatch.caps import CAP_NAMES, fold, spent
from squatch.config import Caps, parse
from squatch.journal import Event


def event(stem: str, cap: str, *, ticket_sha: str | None = "sha") -> Event:
    body = {"cap": cap, "run_seq": 0}
    if ticket_sha is not None:
        body["ticket_sha"] = ticket_sha
    return Event(v=1, type="cap_consumed", ts="2026-08-04T12:00:00+00:00",
                 ticket=stem, key=None, body=body)


def confirm(stem: str, actor: str) -> Event:
    return Event(v=1, type="signal", ts="2026-08-04T12:00:00+00:00",
                 ticket=stem, key=None, body={"kind": "confirm", "actor": actor})


def config():
    return parse({"schema_version": 1, "state_dir": "state", "providers": [],
                  "routing": []}, source="test")


def test_declared_cap_names_are_exactly_the_config_cap_fields():
    assert CAP_NAMES == set(Caps.model_fields)


def test_fold_counts_each_named_cap_separately_for_a_lineage():
    facts = fold([event("stem", "retry"), event("stem", "infra"),
                  event("stem", "retry")])
    assert facts.drawn("stem", "retry") == 2
    assert facts.drawn("stem", "infra") == 1
    assert facts.drawn("stem", "diagnosis") == 0


def test_fold_counts_missing_and_different_ticket_shas_in_the_same_lineage():
    facts = fold([event("stem", "retry", ticket_sha=None),
                  event("stem", "retry", ticket_sha="old"),
                  event("stem", "retry", ticket_sha="new")])
    assert facts.drawn("stem", "retry") == 3


def test_spent_names_the_first_spent_spine_cap_and_none_while_all_remain():
    infra = [event("stem", "infra", ticket_sha=str(n)) for n in range(6)]
    assert spent(config(), infra, "stem") == "infra cap spent (6 of 6 drawn)"
    assert spent(config(), [event("stem", "retry")], "stem") is None


def test_premise_bounce_is_a_spine_cap_and_only_operator_confirm_bounds_the_fold():
    premise = [event("stem", "premise_bounce") for _ in range(2)]
    assert spent(config(), premise, "stem") == "premise_bounce cap spent (2 of 2 drawn)"

    draws = [event("stem", "retry") for _ in range(3)]
    assert fold([*draws, confirm("stem", "operator")]).drawn("stem", "retry") == 0
    assert fold([*draws, confirm("stem", "machine")]).drawn("stem", "retry") == 3
