"""``LogPushGateway`` — the default, simulated push gateway (docs/01 §9; mirrors ``LogGateway``).

No real push provider (Expo/FCM/APNs) is integrated — same reasoning as ``LogGateway`` for
SMS: an account, credentials, and device-token plumbing are out of scope for this prototype
pass. A real provider is a second ``PushGateway`` implementation added later, with no change
to the revocation flow that calls it (NFR9).
"""

from __future__ import annotations

import logging

from app.domain.notify.base import DeliveryResult, PushGateway

logger = logging.getLogger("ebads.notify.log_push_gateway")


class LogPushGateway(PushGateway):
    """Records what would have been pushed; always reports delivered."""

    async def send(self, recipient: str, message: str) -> DeliveryResult:
        logger.info("Push to %s: %s", recipient, message)
        return DeliveryResult(delivered=True)
