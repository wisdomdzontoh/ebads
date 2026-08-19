"""``LogGateway`` — the default, simulated SMS gateway (docs/01 §9; risk table, docs/16).

No real SMS provider (Hubtel/Arkesel/mNotify) is integrated: doing so needs an account,
pricing decisions, and KYC that are explicitly out of scope for this prototype pass (the
project's own risk mitigation for "SMS provider integration blocked" is exactly this —
``LogGateway`` behind the same interface, documented as simulated, not a real send). A real
provider is a second ``SMSGateway`` implementation added later, with no change to the
reservation flow that calls it — the same substitutability argument as the bed adapters
(NFR9).
"""

from __future__ import annotations

import logging

from app.domain.notify.base import DeliveryResult, SMSGateway

logger = logging.getLogger("ebads.notify.log_gateway")


class LogGateway(SMSGateway):
    """Records what would have been sent; always reports delivered."""

    async def send(self, recipient_msisdn: str, message: str) -> DeliveryResult:
        logger.info("SMS to %s: %s", recipient_msisdn, message)
        return DeliveryResult(delivered=True)
