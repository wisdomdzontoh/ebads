"""SMS gateway interface (docs/01-architecture.md §9, docs/09 §9, FR19).

The reservation flow calls this one interface to notify the receiving facility; it is
unaware of which provider (if any) is behind it. SMS rather than an in-app notification
because a facility cannot be assumed to hold an active session, to have installed anything,
or to have reliable internet (docs/01 §9).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryResult:
    """Whether one send attempt reached the gateway successfully."""

    delivered: bool
    detail: str | None = None


class SMSGateway(ABC):
    """Abstract SMS sender (docs/01 §9)."""

    @abstractmethod
    async def send(self, recipient_msisdn: str, message: str) -> DeliveryResult:
        """Send ``message`` to ``recipient_msisdn``; never raises on delivery failure."""
        raise NotImplementedError
