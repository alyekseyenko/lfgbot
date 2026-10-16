import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class EventType(StrEnum):
    lobby_created = "lobby_created"
    member_joined = "member_joined"
    member_left = "member_left"
    lobby_full = "lobby_full"
    lobby_opened = "lobby_opened"
    lobby_closed = "lobby_closed"
    lobby_expired = "lobby_expired"
    lobby_updated = "lobby_updated"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    type: EventType
    lobby_id: UUID
    payload: dict[str, Any] | None = None


Listener = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    async def publish(self, event: DomainEvent) -> None:
        if not self._listeners:
            return
        await asyncio.gather(*(listener(event) for listener in self._listeners))
