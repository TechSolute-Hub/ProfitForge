from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.learning.service import LearningService
from app.learning.verification import OutcomeVerificationService
from app.services.market import get_market_service


async def run_learning_cycle() -> str:
    settings = get_settings()
    verifier = OutcomeVerificationService(settings, get_market_service())
    verified = await verifier.verify_pending()

    service = LearningService(settings)
    try:
        candidate = await service.learn_candidate()
        validated = await service.validate_candidate(candidate.version_id)
    except Exception as exc:
        return (
            f"verified={verified}; candidate=not_promoted; "
            f"reason={type(exc).__name__}: {exc}"
        )

    return (
        f"verified={verified}; candidate={validated.version_id}; "
        "status=VALIDATED; activation=manual"
    )


def main() -> None:
    print(asyncio.run(run_learning_cycle()))


if __name__ == "__main__":
    main()
