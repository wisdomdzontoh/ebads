"""The expiry sweeper process (docs/01-architecture.md §7, §10, FR10, S5).

Runs independently of the API process, on a fixed interval (``SWEEPER_INTERVAL_SEC``),
releasing reservations past ``expires_at`` that were never confirmed by arrival. Docs/01 §10
describes this as the same image, a different entrypoint — ``infra/docker-compose.yml``'s
``sweeper`` service runs this module instead of the API.

    python -m scripts.run_sweeper
"""

from __future__ import annotations

import asyncio
import logging

from app.db.session import get_sessionmaker
from app.domain.sweeper.service import sweep_once
from app.parameters import SWEEPER_INTERVAL_SEC

logger = logging.getLogger("ebads.sweeper")


async def _loop() -> None:
    logging.basicConfig(level=logging.INFO)
    sessionmaker = get_sessionmaker()
    while True:
        async with sessionmaker() as session:
            released = await sweep_once(session)
        if released:
            logger.info("released %d expired reservation(s)", released)
        await asyncio.sleep(SWEEPER_INTERVAL_SEC)


def main() -> None:
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
