"""
Demo Teardown Helper for DataHub.

Provides instructions and cleanup helper functions to reset or tear down the local
DataHub environment and seeded demo assets.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("teardown")


def main() -> None:
    logger.info("=== DataHub Demo Teardown Helper ===")
    logger.info("To remove seeded demo metadata from DataHub UI, run:")
    logger.info("  datahub nuke")
    logger.info("To completely stop and remove the local DataHub Docker containers:")
    logger.info("  datahub docker nuke")
    logger.info("=== Teardown steps logged successfully ===")


if __name__ == "__main__":
    main()
