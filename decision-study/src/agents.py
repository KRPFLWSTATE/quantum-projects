"""Small message-driven components with mailboxes. Not runtime LLMs."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Message:
    topic: str
    payload: dict[str, Any]
    sender: str


class Mailbox:
    def __init__(self, name: str) -> None:
        self.name = name
        self.queue: deque[Message] = deque()

    def send(self, message: Message) -> None:
        self.queue.append(message)

    def recv(self) -> Message | None:
        if not self.queue:
            return None
        return self.queue.popleft()


class Component:
    def __init__(self, name: str) -> None:
        self.name = name
        self.mailbox = Mailbox(name)
        self.state: dict[str, Any] = {}

    def handle(self, message: Message, bus: "Bus") -> None:
        raise NotImplementedError


class Bus:
    def __init__(self) -> None:
        self.components: dict[str, Component] = {}
        self.trace: list[dict[str, Any]] = []

    def register(self, component: Component) -> None:
        self.components[component.name] = component

    def post(self, sender: str, topic: str, payload: dict[str, Any], to: str) -> None:
        message = Message(topic=topic, payload=payload, sender=sender)
        self.trace.append({"from": sender, "to": to, "topic": topic, "keys": sorted(payload)})
        self.components[to].mailbox.send(message)

    def drain(self, max_steps: int = 1000) -> None:
        steps = 0
        while steps < max_steps:
            progressed = False
            for component in self.components.values():
                message = component.mailbox.recv()
                if message is None:
                    continue
                progressed = True
                component.handle(message, self)
            if not progressed:
                return
            steps += 1
        raise RuntimeError("message loop exceeded max_steps")


class Coordinator(Component):
    def __init__(self, persist_path: Any | None = None) -> None:
        super().__init__("coordinator")
        self.persist_path = persist_path
        self.decisions: dict[str, Any] = {}
        if persist_path is not None:
            from pathlib import Path
            import json

            path = Path(persist_path)
            if path.is_file():
                self.decisions = json.loads(path.read_text(encoding="utf-8"))

    def _persist(self) -> None:
        if self.persist_path is None:
            return
        from .hashing import write_json_atomic

        write_json_atomic(self.persist_path, self.decisions)

    def handle(self, message: Message, bus: Bus) -> None:
        if message.topic == "spec.ready":
            bus.post(self.name, "encode.request", message.payload, "encoder")
        elif message.topic == "candidates.ready":
            bus.post(self.name, "validate.request", message.payload, "validator")
        elif message.topic == "decision.final":
            request_id = message.payload.get("request_id")
            if request_id in self.decisions:
                self.state.setdefault("duplicates", []).append(message.payload)
                self.state.setdefault("late_archived", []).append(message.payload)
                return
            self.decisions[request_id] = message.payload
            self.state[f"final:{request_id}"] = True
            self._persist()
        elif message.topic in {"timeout", "spec.updated"}:
            bus.post(self.name, message.topic, message.payload, "validator")


class Encoder(Component):
    def __init__(self, encode_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        super().__init__("encoder")
        self.encode_fn = encode_fn

    def handle(self, message: Message, bus: Bus) -> None:
        if message.topic != "encode.request":
            return
        encoded = self.encode_fn(message.payload)
        bus.post(self.name, "solve.request", encoded, "solver")


class SolverAdapter(Component):
    def __init__(self, solve_fn: Callable[[dict[str, Any]], dict[str, Any]], *, hold: bool = False) -> None:
        super().__init__("solver")
        self.solve_fn = solve_fn
        self.hold = hold
        self.held: dict[str, Any] | None = None

    def handle(self, message: Message, bus: Bus) -> None:
        if message.topic == "solver.release" and self.held is not None:
            result = self.solve_fn(self.held)
            self.held = None
            bus.post(self.name, "candidates.ready", result, "coordinator")
            return
        if message.topic != "solve.request":
            return
        if self.hold:
            self.held = message.payload
            return
        result = self.solve_fn(message.payload)
        bus.post(self.name, "candidates.ready", result, "coordinator")


class Validator(Component):
    def __init__(self, validate_fn: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        super().__init__("validator")
        self.validate_fn = validate_fn

    def handle(self, message: Message, bus: Bus) -> None:
        if message.topic in {"timeout", "spec.updated"}:
            decision = self.validate_fn({**message.payload, "event": message.topic})
            bus.post(self.name, "decision.final", decision, "coordinator")
            return
        if message.topic != "validate.request":
            return
        decision = self.validate_fn(message.payload)
        bus.post(self.name, "decision.final", decision, "coordinator")


def run_actor_workflow(
    spec: dict[str, Any],
    encode_fn: Callable[[dict[str, Any]], dict[str, Any]],
    solve_fn: Callable[[dict[str, Any]], dict[str, Any]],
    validate_fn: Callable[[dict[str, Any]], dict[str, Any]],
    persist_path: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bus = Bus()
    coordinator = Coordinator(persist_path=persist_path)
    bus.register(coordinator)
    bus.register(Encoder(encode_fn))
    bus.register(SolverAdapter(solve_fn))
    bus.register(Validator(validate_fn))
    bus.post("user", "spec.ready", spec, "coordinator")
    bus.drain()
    request_id = spec["request_id"]
    return coordinator.decisions[request_id], bus.trace


def run_monolithic(
    spec: dict[str, Any],
    encode_fn: Callable[[dict[str, Any]], dict[str, Any]],
    solve_fn: Callable[[dict[str, Any]], dict[str, Any]],
    validate_fn: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    encoded = encode_fn(spec)
    candidates = solve_fn(encoded)
    return validate_fn(candidates)
