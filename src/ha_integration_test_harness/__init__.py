"""Home Assistant Integration Test Harness.

A pytest plugin providing fixtures and utilities for integration testing
Home Assistant and AppDaemon configurations in Docker containers.

Public Classes:
    DockerComposeManager: Manages Docker container lifecycle and file I/O.
    HomeAssistant: Client for Home Assistant API interactions.
    AppDaemon: Client for AppDaemon API interactions.
    TimeMachine: Manages time manipulation for deterministic testing.
    ContainerInfo: Information about a running Docker container.

Exceptions:
    IntegrationTestError: Base exception for all harness errors.
    DockerError: Docker operation failures.
    HomeAssistantError: Home Assistant operations and API call failures.
    AppDaemonError: AppDaemon operations and API call failures.
    TimeChangeError: Time manipulation failures.

Pytest Fixtures (auto-registered):
    docker: DockerComposeManager for container lifecycle (session scope)
    home_assistant: HomeAssistant API client (session scope)
    app_daemon: AppDaemon API client (session scope)
    time_machine: TimeMachine for time manipulation (function scope)
"""

from .appdaemon_client import AppDaemon
from .docker_manager import DockerComposeManager, DockerContainer
from .exceptions import (
    AppDaemonClientError,
    DockerError,
    HomeAssistantClientError,
    HomeAssistantTimeoutError,
    IntegrationTestError,
    TimeMachineError,
)
from .homeassistant_client import HomeAssistant
from .time_machine import TimeMachine

try:
    from importlib.metadata import version
except ImportError:
    # Python < 3.8
    from importlib_metadata import version  # type: ignore

__version__ = version("ha_integration_test_harness")

__all__ = [
    "AppDaemon",
    "AppDaemonClientError",
    "DockerComposeManager",
    "DockerContainer",
    "DockerError",
    "HomeAssistant",
    "HomeAssistantClientError",
    "HomeAssistantTimeoutError",
    "IntegrationTestError",
    "TimeMachine",
    "TimeMachineError",
]
