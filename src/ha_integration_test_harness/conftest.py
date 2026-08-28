"""Pytest configuration and fixtures for integration tests."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator, Optional

import pytest

from .appdaemon_client import AppDaemon
from .docker_manager import DockerComposeManager
from .exceptions import HomeAssistantTimeoutError
from .homeassistant_client import HomeAssistant
from .time_machine import TimeMachine

logger = logging.getLogger(__name__)

# Session-level flag to capture diagnostics only once
_diagnostics_captured = False
_failure_key: pytest.StashKey[bool] = pytest.StashKey()
_docker_manager_key: pytest.StashKey[Optional[DockerComposeManager]] = pytest.StashKey()
_home_assistant_key: pytest.StashKey[Optional[HomeAssistant]] = pytest.StashKey()
_test_start_time_key: pytest.StashKey[Optional[datetime]] = pytest.StashKey()


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]) -> None:
    """Pytest hook to detect test failures and mark for diagnostics capture.

    When a HomeAssistantTimeoutError is detected, confirms unresponsiveness via
    ``check_health()``, captures container diagnostics, and sets the ``is_unresponsive``
    flag so remaining tests are skipped and cleanup is suppressed.
    """
    global _diagnostics_captured

    if call.when == "call" and call.excinfo is not None:
        if isinstance(call.excinfo.value, HomeAssistantTimeoutError):
            home_assistant = item.session.stash.get(_home_assistant_key, None)
            docker_manager = item.session.stash.get(_docker_manager_key, None)

            if home_assistant is not None:
                healthy = home_assistant.check_health()
                if not healthy:
                    logger.warning("Home Assistant confirmed UNREACHABLE after timeout — remaining tests will be skipped")
                    if docker_manager is not None and not _diagnostics_captured:
                        test_name = item.nodeid
                        test_duration = call.duration if hasattr(call, "duration") else None
                        logger.warning(f"Home Assistant request timed out\n" f"{docker_manager.get_container_diagnostics(test_name=test_name, test_duration=test_duration)}")
                        _diagnostics_captured = True

        if not item.session.stash.get(_failure_key, False):
            item.session.stash[_failure_key] = True


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Capture test start time for assertion diagnostics."""
    now = datetime.now()
    item.session.stash[_test_start_time_key] = now
    home_assistant = item.session.stash.get(_home_assistant_key, None)
    if home_assistant is not None:
        home_assistant._test_start_time = now


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom pytest configuration options for the harness.

    Adds the 'ha_persistent_entities_path' config key to allow test suites
    to specify a YAML file containing persistent entity definitions
    that should be registered with Home Assistant during container startup.
    """
    parser.addini(
        "ha_persistent_entities_path",
        "Path to YAML file containing persistent Home Assistant entities (relative to pytest config file)",
        default=None,
    )


@pytest.fixture(scope="session")
def docker(request: pytest.FixtureRequest) -> Generator[DockerComposeManager, None, None]:
    """Provide Docker Compose manager for integration tests.

    This fixture creates and starts Docker containers for Home Assistant and AppDaemon,
    managing their lifecycle for the entire test session (scope="session") to avoid
    the overhead of repeatedly starting and stopping containers.

    Persistent entities can be registered during container startup by providing
    a YAML file path via the 'ha_persistent_entities_path' pytest configuration option.

    The containers are automatically cleaned up after all tests in the session complete.

    Args:
        request: The pytest request object for accessing configuration options.

    Yields:
        DockerComposeManager: Manager for Docker container lifecycle and file operations.
    """
    global _diagnostics_captured

    # Get persistent entities path from pytest configuration if provided
    persistent_entities_path = request.config.getini("ha_persistent_entities_path")

    # Resolve relative paths against the active pytest config file directory
    if persistent_entities_path:
        entities_path = Path(str(persistent_entities_path))
        if not entities_path.is_absolute():
            inipath = getattr(request.config, "inipath", None)
            if inipath is None:
                raise pytest.UsageError(
                    "ha_persistent_entities_path is a relative path, but no pytest config file (e.g. pytest.ini, pyproject.toml) was found. "
                    "Either use an absolute path or run pytest from a directory containing a config file."
                )
            entities_path = Path(str(inipath)).parent / entities_path
        persistent_entities_path = str(entities_path)

    manager: Optional[DockerComposeManager] = None
    try:
        manager = DockerComposeManager(persistent_entities_path=persistent_entities_path)
        # Store the manager in session stash so it can be accessed by hooks
        request.session.stash[_docker_manager_key] = manager
        manager.start()
        logger.info("Docker containers started successfully")
        yield manager
    except Exception:
        diag = manager.get_container_diagnostics() if manager is not None else ""
        logger.warning(f"Container startup failed\n{diag}")
        _diagnostics_captured = True
        raise
    finally:
        if manager is not None:
            # Capture diagnostics if any failures detected
            test_failures = request.session.testsfailed > 0
            hook_failures = request.session.stash.get(_failure_key, False)
            container_failure = not manager.containers_healthy()

            if (test_failures or hook_failures or container_failure) and not _diagnostics_captured:
                logger.warning(manager.get_container_diagnostics())
                _diagnostics_captured = True

            logger.info("Tearing down Docker containers")
            manager.stop()


@pytest.fixture(scope="session")
def home_assistant(request: pytest.FixtureRequest, docker: DockerComposeManager) -> HomeAssistant:
    """Provide Home Assistant API client for integration tests.

    This fixture creates a Home Assistant client configured with the dynamically
    assigned URL and long-lived access token from the Docker container. The client
    is shared across all tests in the session (scope="session").

    Args:
        request: The pytest request object for accessing session stash.
        docker: The Docker container manager fixture.

    Returns:
        HomeAssistant: Client for Home Assistant API interactions.
    """
    base_url = docker.get_home_assistant_url()
    access_token = docker.read_container_file("homeassistant", "/shared_data/.ha_token")
    ha = HomeAssistant(base_url, access_token)
    request.session.stash[_home_assistant_key] = ha
    return ha


@pytest.fixture(scope="session")
def app_daemon(docker: DockerComposeManager) -> AppDaemon:
    """Provide AppDaemon API client for integration tests.

    This fixture creates an AppDaemon client configured with the dynamically
    assigned URL from the Docker container. The client is shared across all tests
    in the session (scope="session").

    Args:
        docker: The Docker container manager fixture.

    Returns:
        AppDaemon: Client for AppDaemon API interactions.
    """
    base_url = docker.get_appdaemon_url()
    return AppDaemon(base_url)


@pytest.fixture(scope="session")
def time_machine(docker: DockerComposeManager, home_assistant: HomeAssistant) -> TimeMachine:
    """Provide time machine for integration tests.

    This fixture creates a time machine that allows tests to advance time forward
    for deterministic testing of time-based automations. Time control is implemented
    via WebSocket commands to the ha_test_harness custom component, which applies
    an in-process time offset to HA's time functions.

    **IMPORTANT**: The public API (fast_forward, jump_to_next) only moves time forward.
    The fixture is session-scoped, meaning time persists across all tests in the session.
    Tests that depend on specific time conditions must explicitly advance time to the
    desired state at the start of the test.

    Tests must explicitly request this fixture to use time manipulation.

    Args:
        docker: The Docker container manager fixture.
        home_assistant: The Home Assistant client fixture.

    Returns:
        TimeMachine: Manager for time manipulation operations.
    """
    try:
        ha_config = home_assistant.get_config()
        timezone_str = ha_config.get("time_zone")
    except Exception as e:
        raise RuntimeError(f"time_machine fixture: failed to fetch Home Assistant config at session startup — is Home Assistant healthy? Underlying error: {e}") from e

    def _apply_time_change(target_dt: datetime) -> None:
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        timestamp_str = target_dt.isoformat()
        home_assistant.ws_time_set(timestamp_str)

    def _advance_time(delta: timedelta) -> None:
        home_assistant.ws_time_advance(delta.total_seconds())

    def _get_current_time_ws() -> datetime:
        result = home_assistant.ws_time_get()
        return datetime.fromisoformat(result["timestamp"])

    try:
        return TimeMachine(
            apply_time_change=_apply_time_change,
            advance_time=_advance_time,
            get_current_time_ws=_get_current_time_ws,
            get_entity_state=lambda entity_id: home_assistant.get_state(entity_id),
            timezone=timezone_str,
        )
    except ValueError as e:
        raise RuntimeError(
            f"time_machine fixture: Home Assistant returned an unrecognised timezone '{timezone_str}'. Check the 'time_zone' field in your HA configuration.yaml. Underlying error: {e}"
        ) from e

    # No teardown: time cannot be reset and persists across tests in the session


@pytest.fixture(autouse=True)
def _skip_if_unresponsive(request: pytest.FixtureRequest) -> None:
    """Skip remaining tests if Home Assistant has been confirmed unresponsive.

    This autouse fixture runs before each test. If the test uses the ``home_assistant``
    fixture and Home Assistant has been marked unresponsive (via a timeout + failed health
    check), the test is skipped immediately. This prevents a cascade of ~40 timeout errors
    when HA becomes unresponsive mid-suite.

    Also captures the test start time for assertion diagnostics.

    Args:
        request: The pytest request object for conditional fixture access.
    """
    if "home_assistant" in request.fixturenames:
        home_assistant: HomeAssistant = request.getfixturevalue("home_assistant")
        home_assistant._test_start_time = datetime.now()
        if home_assistant.is_unresponsive:
            pytest.skip("Home Assistant is unresponsive")


@pytest.fixture(autouse=True)
def _cleanup_test_entities(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Auto-cleanup fixture that removes test entities and restores entity config after each test.

    This fixture automatically runs after every test function (autouse=True) and:

    - Calls ``restore_entity_config()`` to undo any label or area changes made via
      ``given_entity_has()`` during the test.
    - Calls ``restore_entity_states()`` to undo any state changes made via
      ``set_state()`` during the test.
    - Calls ``clean_up_test_entities()`` to remove any entities created via
      ``given_an_entity()``.

    Tests don't need to explicitly request this fixture.

    Only activates cleanup if the test actually used the home_assistant fixture,
    avoiding unnecessary Docker container startup for tests that don't need it.
    Cleanup is skipped if Home Assistant has been confirmed unresponsive (futile
    when the API is down).

    Args:
        request: The pytest request object for conditional fixture access.

    Yields:
        None: This fixture doesn't provide any value to tests.
    """
    # Setup: nothing to do before the test
    yield

    # Teardown: only clean up if the test used home_assistant fixture
    if "home_assistant" in request.fixturenames:
        home_assistant: HomeAssistant = request.getfixturevalue("home_assistant")
        if home_assistant.is_unresponsive:
            return
        try:
            home_assistant.restore_entity_config()
        finally:
            try:
                home_assistant.restore_entity_states()
            finally:
                home_assistant.clean_up_test_entities()
