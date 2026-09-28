"""Replay-safe escalation delivery from durable daemon signals."""

from collections.abc import Callable, Sequence
from urllib.parse import quote

from squatch.effects import Effects, effect_key
from squatch.journal import Journal
from squatch.seams import ExecutableNotFound, Notifications
from squatch.storm import StormLedger


class NotificationReconciler:
    def __init__(self, *, journal: Journal, notifications: Notifications,
                 argv: Sequence[str], report: Callable[[str], None]) -> None:
        self._journal = journal
        self._notifications = notifications
        self._argv = tuple(argv)
        self._report = report
        self._effects = Effects(journal)

    async def reconcile(self) -> None:
        for ticket, kind, identity, rendered in self._escalations():
            key = effect_key("notify", quote(ticket or "-", safe=""), kind, identity)

            async def deliver() -> None:
                await self._notifications.notify([*self._argv, rendered])
                self._report(rendered)

            try:
                # Delivery cannot be observed externally: unmatched intents resend.
                await self._effects.run(deliver, key=key, ticket=ticket)
            except (ExecutableNotFound, RuntimeError, TimeoutError) as error:
                self._report(f"notification failed ({key}): {type(error).__name__}; "
                             "check config.notify and its command; retry on next poll")

    def _escalations(self):
        events = tuple(self._journal.read())
        holds = {}
        released_storm_trips = set()
        for event in events:
            body = event.body
            if event.type == "signal" and body.get("kind") == "control_hold":
                if body.get("released") is True:
                    held = holds.pop(body["hold_id"], None)
                    if held is not None and held.get("trigger") == "storm_trip":
                        released_storm_trips.add(held["trip_id"])
                elif body.get("released") is False:
                    holds[body["hold_id"]] = body
        storm_holds = {body["trip_id"]: hold_id for hold_id, body in holds.items()
                       if body.get("trigger") == "storm_trip"}
        for trip in StormLedger(journal=self._journal).trips():
            identity, ticket = trip["trip_id"], trip["emitting_origin"]
            if identity in released_storm_trips:
                continue
            hold_id = storm_holds.get(identity)
            if hold_id is not None:
                action = f"After inspection: squatch resume --hold-id {hold_id}"
            else:
                action = (
                    "No active hold exists. When this origin is next offered, inspect "
                    f"the journal for its unreleased control_hold with trip_id {identity}; "
                    "run squatch resume with that record's --hold-id after inspection. "
                    "A pending trip cannot be resumed before its hold exists.")
            yield ticket, "storm_trip", identity, (
                f"storm-breaker trip: {identity}; origin: {ticket}; "
                f"signature: {trip['signature']}\n{action}")
        for event in events:
            body = event.body
            if (event.type == "signal" and body.get("kind") == "control_hold"
                    and body.get("trigger") == "integration_red_streak"
                    and body.get("released") is False
                    and body["hold_id"] in holds):
                identity = body["hold_id"]
                yield event.ticket, "integration_red_streak", identity, (
                    f"integration-red streak: merge admissions paused; ticket: {event.ticket}\n"
                    f"After inspection: squatch resume --hold-id {identity}")

            if (event.type == "signal" and body.get("kind") == "watchdog"
                    and body.get("spiral") in ("spend_without_progress", "stuck")
                    and isinstance(body.get("ticket"), str) and body["ticket"]
                    and event.ticket == body["ticket"]
                    and type(body.get("run_seq")) is int):
                spiral = body["spiral"]
                identity = str(body["run_seq"]) if spiral == "spend_without_progress" else "stuck"
                yield event.ticket, spiral, identity, (
                    f"watchdog {spiral}: ticket {event.ticket}; run {body['run_seq']}\n"
                    "Inspect the run artifacts; squatch kill stops active work.")
