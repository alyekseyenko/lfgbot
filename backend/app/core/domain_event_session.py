"""Publica eventos de domínio apenas após commit da transação SQLAlchemy."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.events import DomainEvent

if TYPE_CHECKING:
    from app.core.events import EventBus

logger = logging.getLogger(__name__)

_PENDING_KEY = "_pending_domain_events"
_bus: EventBus | None = None
_hooks_registered = False


def set_domain_event_bus(bus: EventBus) -> None:
    global _bus
    _bus = bus
    _ensure_hooks()


def queue_domain_event(session: AsyncSession, domain_event: DomainEvent) -> None:
    sync = session.sync_session
    pending: list[DomainEvent] = sync.info.setdefault(_PENDING_KEY, [])
    pending.append(domain_event)


def _ensure_hooks() -> None:
    global _hooks_registered
    if _hooks_registered:
        return
    target = AsyncSession.sync_session_class

    @event.listens_for(target, "after_commit")
    def _after_commit(sync_session: Session) -> None:
        pending: list[DomainEvent] | None = sync_session.info.pop(_PENDING_KEY, None)
        if not pending or _bus is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("domain events pending but no running event loop")
            return
        for item in pending:
            loop.create_task(
                _bus.publish(item),
                name=f"domain-event-{item.type.value}",
            )

    @event.listens_for(target, "after_rollback")
    def _after_rollback(sync_session: Session) -> None:
        sync_session.info.pop(_PENDING_KEY, None)

    _hooks_registered = True
