"""Notification gateway interfaces (docs/01-architecture.md §9, docs/09 §9, FR19, FR24-27).

Two channels, two audiences. ``SMSGateway`` notifies the *facility* on a successful
reservation — a facility cannot be assumed to hold an active session, to have installed
anything, or to have reliable internet (docs/01 §9). ``PushGateway`` notifies the
*dispatcher* on revocation (FR24-27): the dispatcher is a moving vehicle, not a fixed line,
so push reaches an open app session directly, and SMS is sent alongside it as the fallback
that does not depend on one being open.
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


class PushGateway(ABC):
    """Abstract push notification sender — the dispatcher's channel (FR24-27).

    Same substitutability argument as ``SMSGateway`` and the bed adapters (NFR9): the
    revocation flow calls this one interface, unaware of which provider (if any) is behind
    it. No real provider (Expo/FCM/APNs) is integrated — an account and platform-specific
    device-token plumbing are out of scope for this prototype pass, the same reasoning
    ``LogGateway`` already documents for SMS.
    """

    @abstractmethod
    async def send(self, recipient: str, message: str) -> DeliveryResult:
        """Send ``message`` to ``recipient``; never raises on delivery failure."""
        raise NotImplementedError
