"""Typed durable requests for the journal lock holder."""

from collections.abc import Awaitable, Callable
from hashlib import sha256
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from squatch.journal import Journal
from squatch.seams import Filesystem


Action = Literal["pause", "release", "kill"]
Outcome = Literal["accepted", "stale", "conflict", "invalid"]


class ControlRequest(BaseModel):
    """One immutable request addressed to an engine lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    v: Literal[1] = 1
    request_id: UUID = Field(default_factory=uuid4)
    action: Action
    lifecycle: UUID
    hold_id: UUID | None = None

    @model_validator(mode="after")
    def release_names_exactly_one_hold(self) -> "ControlRequest":
        if (self.action == "release") != (self.hold_id is not None):
            raise ValueError("hold_id is required only for release requests")
        return self


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

    @property
    def holds(self) -> frozenset[UUID]:
        return frozenset(self._holds)

    def hold(self) -> UUID:
        """Create a never-reused hold identity for a later bound release."""
        hold_id = uuid4()
        self._holds.add(hold_id)
        return hold_id

    async def consume(self, mutate: Mutation) -> tuple[ControlDecision, ...]:
        """Consume one stable snapshot, retrying only incomplete accepted work."""
        decisions = self._decisions()
        consumed = []
        for path in self._fs.list(self._directory, "*.json"):
            decision = await self._consume(path, decisions, mutate)
            decisions[path.stem] = decision
            consumed.append(decision)
        return tuple(consumed)

    async def _consume(self, path: Path, decisions: dict[str, ControlDecision],
                       mutate: Mutation) -> ControlDecision:
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
        elif request.action == "release" and request.hold_id not in self._holds:
            decision = ControlDecision(
                outcome="stale", request=request, reason="hold does not match")
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
            self._holds.discard(request.hold_id)
        await mutate(request)

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
