"""Custom exception types for the integration test harness."""


class IntegrationTestError(Exception):
    """Base exception for all harness-related errors.

    All custom exceptions in the harness package inherit from this base class,
    allowing callers to catch all harness exceptions with a single except clause.
    """

    pass


class DockerError(IntegrationTestError):
    """Exception raised when Docker operations fail.

    This includes failures in:
    - Starting or stopping containers
    - Reading or writing files from containers
    - Port mapping discovery
    - Container diagnostics retrieval
    """

    pass


class HomeAssistantClientError(IntegrationTestError):
    """Exception raised when Home Assistant operations fail.

    This is the base exception for all Home Assistant-related errors,
    including authentication failures and API call failures.

    This includes failures in:
    - Setting entity states
    - Getting entity states
    - Removing entities
    - Other HTTP API interactions
    """

    pass


class HomeAssistantTimeoutError(HomeAssistantClientError):
    """Exception raised when a Home Assistant HTTP request times out.

    This is a specialized exception for timeout failures, allowing callers
    to distinguish between timeouts and other API errors. Inherits from
    HomeAssistantClientError for backwards compatibility.

    This includes failures in:
    - HTTP request timeouts (GET, POST, DELETE)
    - Socket timeouts
    - Connection timeouts
    """

    pass


class AppDaemonClientError(IntegrationTestError):
    """Exception raised when AppDaemon operations fail.

    This includes failures in:
    - AppDaemon API interactions
    - App state queries
    - Service calls to AppDaemon
    """

    pass


class TimeMachineError(IntegrationTestError):
    """Exception raised when time manipulation operations fail.

    This includes failures in:
    - Setting time via libfaketime
    - Advancing time
    - Resetting time to real time
    - Writing faketime configuration files
    """

    pass


class PersistentEntityError(IntegrationTestError):
    """Exception raised when persistent entity registration fails.

    This includes failures in:
    - Loading or parsing persistent entities YAML file
    - Validating persistent entity definitions
    - Staging configuration directories before container startup
    """

    pass
