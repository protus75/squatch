"""Typed durable requests for the journal lock holder."""

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from squatch.artifacts import Cost
from squatch.journal import Journal
from squatch.seams import Filesystem


Action = Literal["pause", "release", "confirm", "kill"]
Outcome = Literal["accepted", "stale", "conflict", "invalid"]
Actor = Literal["operator", "machine"]


class ControlRequest(BaseModel):
    """One immutable request addressed to an engine lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1] = 1
    request_id: UUID = Field(default_factory=uuid4)
    action: Action
    lifecycle: UUID
    hold_id: UUID | None = None
    stem: str | None = None
    actor: Actor | None = None

    @model_validator(mode="after")
    def release_names_exactly_one_hold(self) -> "ControlRequest":
        bound = self.action in {"release", "confirm"}
        if bound != (self.hold_id is not None):
            raise ValueError("hold_id is required only for release and confirm requests")
        if self.action == "confirm":
            if not self.stem or self.actor not in {"operator", "machine"}:
                raise ValueError("confirm requires a stem and actor")
        elif self.stem is not None or self.actor is not None:
            raise ValueError("stem and actor are valid only for confirm requests")
        return self


@dataclass(frozen=True)
class SupervisedMergeHold:
    """The durable authority needed to resume one checked admission."""

    hold_id: UUID
    lifecycle: UUID
    stem: str
    run_seq: int
    worktree: Path
    reviewed_sha: str | None
    candidate_sha: str
    outcome: str
    verdict: str
    summary: str
    base: str
    cost: Cost


def supervised_merge_holds(events: Iterable) -> dict[str, SupervisedMergeHold]:
    """Project active HELD admissions, with a merged terminal closing custody."""
    active: dict[UUID, SupervisedMergeHold] = {}
    merged: set[str] = set()
    for event in events:
        body = getattr(event, "body", {})
        if (getattr(event, "type", None) == "state_transition"
                and body.get("to") == "merged" and event.ticket is not None):
            merged.add(event.ticket)
            continue
        if getattr(event, "type", None) != "signal" or body.get("kind") != "control_hold":
            continue
        try:
            hold_id = UUID(body["hold_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if body.get("released") is True:
            active.pop(hold_id, None)
            continue
        if body.get("released") is not False or body.get("trigger") != "supervised_merge":
            continue
        try:
            record = SupervisedMergeHold(
                hold_id=hold_id, lifecycle=UUID(body["lifecycle"]), stem=body["stem"],
                run_seq=body["run_seq"], worktree=Path(body["worktree"]),
                reviewed_sha=body.get("reviewed_sha"), candidate_sha=body["candidate_sha"],
                outcome=body["outcome"], verdict=body["verdict"], summary=body["summary"],
                base=body["base"], cost=Cost(**body["cost"]))
        except (KeyError, TypeError, ValueError):
            continue
        if (type(record.stem) is str and record.stem and type(record.run_seq) is int
                and record.run_seq >= 0 and type(record.candidate_sha) is str
                and type(record.outcome) is str and type(record.verdict) is str
                and type(record.summary) is str and type(record.base) is str):
            active[hold_id] = record
    return {record.stem: record for record in active.values() if record.stem not in merged}


class ControlDecision(BaseModel):
    """The journal projection for a request's committed disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["control_decision"] = "control_decision"
    outcome: Outcome
    request: ControlRequest | None
    reason: str | None = None
    applied: bool = False
    invalid_digest: str | None = None


# Only incomplete accepted work is retried. A callback must use request_id as
# its idempotency key for a failure after mutation but before the applied
# marker; the journal cannot atomically commit an external callback's state.
Mutation = Callable[[ControlRequest], Awaitable[None]]


def publish_control(state_dir: Path, request: ControlRequest, fs: Filesystem) -> Path:
    """Publish without opening the single-writer journal or replacing a request."""
    path = Path(state_dir) / "control" / f"{request.request_id}.json"
    fs.publish(path, request.model_dump_json().encode())
    return path


class ControlInbox:
    """Consume durable control files under the lock holder's Journal."""

    def __init__(self, state_dir: Path, *, journal: Journal, fs: Filesystem,
                 lifecycle: UUID | None = None) -> None:
        self._directory = Path(state_dir) / "control"
        self._journal = journal
        self._fs = fs
        self.lifecycle = lifecycle or uuid4()
        self._holds: set[UUID] = set()
        self._confirm: Mutation | None = None

    def bind_confirm(self, confirm: Mutation) -> None:
        """Bind the one production admission path that a confirm may resume."""
        self._confirm = confirm

    @property
    def holds(self) -> frozenset[UUID]:
        return frozenset(self._holds)

    def hold(self, hold_id: UUID | None = None) -> UUID:
        """Create a never-reused hold identity for a later bound release."""
        hold_id = hold_id or uuid4()
        if hold_id in self._holds:
            raise ValueError("hold identity is already active")
        self._holds.add(hold_id)
        self._journal.append("signal", {"kind": "control_hold", "hold_id": str(hold_id),
                                        "lifecycle": str(self.lifecycle), "released": False})
        return hold_id

    def discard_hold(self, hold_id: UUID) -> None:
        """Retire a superseded hold so its release cannot affect a successor."""
        if hold_id in self._holds:
            self._holds.discard(hold_id)
            self._journal.append("signal", {"kind": "control_hold", "hold_id": str(hold_id),
                                            "lifecycle": str(self.lifecycle), "released": True})

    @classmethod
    def active_lifecycle(cls, journal: Journal) -> UUID | None:
        """Keep the lifecycle of a durable hold or unfinished accepted work."""
        active: dict[tuple[str, str], UUID] = {}
        for event in journal.read():
            body = event.body
            if event.type != "signal":
                continue
            if body.get("kind") == "control_decision" and event.key is not None:
                decision = ControlDecision.model_validate(body)
                key = ("decision", event.key)
                active.pop(key, None)
                if decision.outcome == "accepted" and not decision.applied:
                    assert decision.request is not None
                    active[key] = decision.request.lifecycle
                continue
            if body.get("kind") != "control_hold":
                continue
            try:
                hold_id, lifecycle = UUID(body["hold_id"]), UUID(body["lifecycle"])
            except (KeyError, TypeError, ValueError):
                continue
            if body.get("released") is True:
                active.pop(("hold", str(hold_id)), None)
            elif body.get("released") is False:
                active[("hold", str(hold_id))] = lifecycle
        return next(reversed(active.values()), None) if active else None

    def rehydrate_holds(self) -> None:
        """Restore this lifecycle's unreleased hold identities from the journal."""
        self._holds.clear()
        for event in self._journal.read():
            body = event.body
            if event.type != "signal" or body.get("kind") != "control_hold":
                continue
            try:
                hold_id, lifecycle = UUID(body["hold_id"]), UUID(body["lifecycle"])
            except (KeyError, TypeError, ValueError):
                continue
            if lifecycle != self.lifecycle:
                continue
            if body.get("released") is True:
                self._holds.discard(hold_id)
            elif body.get("released") is False:
                self._holds.add(hold_id)

    async def consume(self, mutate: Mutation) -> tuple[ControlDecision, ...]:
        """Consume one stable snapshot, retrying only incomplete accepted work."""
        decisions = self._decisions()
        releasable = frozenset(self._holds)
        consumed = []
        for path in self._fs.list(self._directory, "*.json"):
            decision = await self._consume(path, decisions, releasable, mutate)
            decisions[path.stem] = decision
            consumed.append(decision)
        return tuple(consumed)

    async def _consume(self, path: Path, decisions: dict[str, ControlDecision],
                       releasable: frozenset[UUID], mutate: Mutation) -> ControlDecision:
        raw = self._fs.read(path)
        try:
            request = ControlRequest.model_validate_json(raw)
            # Wire identities must survive replay, never be minted while reading.
            if "request_id" not in request.model_fields_set:
                raise ValueError("request_id is missing")
        except (ValidationError, ValueError) as error:
            decision = ControlDecision(
                outcome="invalid", request=None, reason=type(error).__name__,
                invalid_digest=sha256(raw).hexdigest())
            # Invalid payloads have no typed identity to compare on replay.
            if decisions.get(path.stem) != decision:
                self._append(path.stem, decision)
            self._fs.remove(path)
            return decision

        request_id = str(request.request_id)
        if path.stem != request_id:
            decision = ControlDecision(
                outcome="invalid", request=request, reason="request_id does not match filename")
            if decisions.get(path.stem) != decision:
                self._append(path.stem, decision)
            self._fs.remove(path)
            return decision

        existing = decisions.get(request_id)
        if existing is not None:
            if existing.request != request:
                decision = ControlDecision(
                    outcome="conflict", request=request, reason="request_id was already decided")
                self._append(request_id, decision)
                self._fs.remove(path)
                return decision
            if existing.outcome != "accepted":
                self._fs.remove(path)
                return existing
            if existing.applied:
                self._fs.remove(path)
                return existing
            if request.lifecycle != self.lifecycle:
                decision = ControlDecision(
                    outcome="stale", request=request, reason="accepted lifecycle ended")
                self._append(request_id, decision)
                self._fs.remove(path)
                return decision
            await self._apply(request, mutate)
            completed = existing.model_copy(update={"applied": True})
            self._append(request_id, completed)
            self._fs.remove(path)
            return completed

        if request.lifecycle != self.lifecycle:
            decision = ControlDecision(
                outcome="stale", request=request, reason="lifecycle does not match")
        elif request.action in {"release", "confirm"} and request.hold_id not in releasable:
            decision = ControlDecision(
                outcome="stale", request=request, reason="hold does not match")
        elif request.action == "release" and any(
                record.hold_id == request.hold_id
                for record in supervised_merge_holds(self._journal.read()).values()):
            decision = ControlDecision(
                outcome="invalid", request=request,
                reason="supervised merge holds require confirm")
        elif request.action == "confirm" and (
                (hold := supervised_merge_holds(self._journal.read()).get(request.stem))
                is None or hold.hold_id != request.hold_id):
            decision = ControlDecision(
                outcome="stale", request=request, reason="stem does not match hold")
        else:
            decision = ControlDecision(outcome="accepted", request=request)
        self._append(request_id, decision)
        if decision.outcome == "accepted":
            await self._apply(request, mutate)
            decision = decision.model_copy(update={"applied": True})
            self._append(request_id, decision)
        self._fs.remove(path)
        return decision

    async def _apply(self, request: ControlRequest, mutate: Mutation) -> None:
        if request.action == "release":
            assert request.hold_id is not None
            self.discard_hold(request.hold_id)
        await mutate(request)
        if request.action == "confirm":
            if self._confirm is None:
                raise RuntimeError("supervised confirm has no admission consumer")
            assert request.hold_id is not None
            await self._confirm(request)
            self.discard_hold(request.hold_id)

    async def confirm(self, stem: str, hold_id: UUID, *, actor: Actor) -> ControlDecision:
        """Apply a direct, lock-held confirm through the same durable inbox path."""
        request = ControlRequest(action="confirm", lifecycle=self.lifecycle,
                                 hold_id=hold_id, stem=stem, actor=actor)
        publish_control(self._directory.parent, request, self._fs)

        async def no_other_mutation(_request: ControlRequest) -> None:
            return None

        return await self._consume(
            self._directory / f"{request.request_id}.json", self._decisions(),
            frozenset(self._holds), no_other_mutation)

    def _append(self, request_id: str, decision: ControlDecision) -> None:
        self._journal.append(
            "signal", decision.model_dump(mode="json"), key=f"control/{request_id}")

    def _decisions(self) -> dict[str, ControlDecision]:
        decisions = {}
        for event in self._journal.read():
            if (event.type == "signal" and event.key is not None
                    and event.key.startswith("control/")
                    and event.body.get("kind") == "control_decision"):
                decisions[event.key.removeprefix("control/")] = (
                    ControlDecision.model_validate(event.body))
        return decisions
