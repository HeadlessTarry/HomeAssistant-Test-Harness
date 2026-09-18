# Available Fixtures

The harness provides four pytest fixtures that are automatically available when the package is installed.

All fixtures are **session-scoped**:

- Created once when first test requests them
- Shared across all tests in the session
- Torn down after all tests complete
- Provides fast test execution (containers start once)
- **Time and entity states persist across tests**

## Fixture Documentation

- **[Home Assistant Fixture](home-assistant-fixture.md)** — When interacting with Home Assistant: entity management, state assertions, action calls, area/label assignment
- **[AppDaemon Fixture](app-daemon-fixture.md)** — When working with AppDaemon: basic API access
- **[Time Machine Fixture](time-machine-fixture.md)** — When testing time-based automations: forward-only constraint, DST handling, session-scoped persistence, sunrise/sunset presets

## `docker` (session scope)

Manages Docker container lifecycle for the entire test session.

### docker API

```python
docker.get_home_assistant_url() -> str
docker.get_appdaemon_url() -> str
docker.read_container_file(service: str, file_path: str) -> str
docker.write_container_file(service: str, file_path: str, content: str) -> None
docker.get_container_diagnostics() -> str
docker.containers_healthy() -> bool
```

### docker Usage

Most tests won't interact with `docker` directly. The `home_assistant` and `app_daemon` fixtures provide higher-level APIs.

```python
def test_with_docker(docker):
    # Get container diagnostics for debugging
    print(docker.get_container_diagnostics())
```
