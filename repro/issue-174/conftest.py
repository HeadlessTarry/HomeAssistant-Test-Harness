"""Pytest configuration for issue #174 reproduction tests.

This conftest.py configures the test environment for reproducing the HA unresponsiveness
issue. The tests run WITHOUT any workaround to validate whether the v0.15.3 fix is effective.
"""

import logging

logger = logging.getLogger(__name__)


def pytest_configure(config: object) -> None:
    """Configure pytest for issue #174 reproduction."""
    logger.info("[REPRO] Running issue #174 reproduction tests WITHOUT workaround")
    logger.info("[REPRO] These tests should expose the asyncio event loop blockage if present")
