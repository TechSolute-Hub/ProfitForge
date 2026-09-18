from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.learning.service import LearningService


async def promote(version_id: str) -> None:
    version = await LearningService(get_settings()).activate(version_id)
    print(
        f"activated={version.version_id}; "
        f"model_family={version.model_family}; status={version.status.value}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activate a previously validated research model version."
    )
    parser.add_argument("version_id")
    args = parser.parse_args()
    asyncio.run(promote(args.version_id))


if __name__ == "__main__":
    main()
