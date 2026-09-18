# Usage Guide

## Overview

The integration test harness provides a complete Docker-based test environment for
Home Assistant and AppDaemon. Tests run against real instances, not mocks, ensuring
your configuration works correctly.

## Installation

See [Installation Guide](installation.md) for details.

## Auto-Discovery

When you run tests, the harness:

1. **Checks environment variables**: Looks for `HA_CONFIG_ROOT` (Home Assistant) and `APPDAEMON_CONFIG_ROOT` (AppDaemon)
2. **Falls back to subdirectories**: If environment variables are not set, looks for `home_assistant/` and `appdaemon/` subdirectories in the current working directory
3. **Validates configuration**:
   - Checks that `configuration.yaml` exists in the Home Assistant root (raises error if missing)
   - Checks that `apps/apps.yaml` exists in the AppDaemon root (logs warning if missing)
4. **Mounts directories**: Mounts the directories as `/config` in the Home Assistant container and `/conf/apps` in the AppDaemon container

**Note:** You can run tests from any directory by using either:

**Option 1 - Use default directory structure** (recommended):

```text
my-project/
├── home_assistant/          # Home Assistant configuration
│   └── configuration.yaml
├── appdaemon/              # AppDaemon configuration
│   └── apps/
│       └── apps.yaml
└── tests/                  # Your test files
    └── test_integration.py
```

**Option 2 - Set environment variables explicitly**:

```bash
export HA_CONFIG_ROOT=/path/to/homeassistant/config
export APPDAEMON_CONFIG_ROOT=/path/to/appdaemon/config
pytest
```

If neither environment variables are set nor the default subdirectories exist, configuration validation will fail.

## Container Lifecycle

- **Session-scoped**: Containers start once per test session and are shared across all tests
- **Automatic cleanup**: Containers are stopped and removed after all tests complete
- **Parallel-safe**: Dynamic port allocation allows multiple test runs concurrently

## Configuration Requirements

Your Home Assistant repository must contain:

- `configuration.yaml` at the root
- Valid Home Assistant configuration structure
- Any referenced files (automations, scripts, templates, etc.)

The harness mounts your entire repository, so all files are available to Home Assistant.

## Documentation

- **[Architecture](architecture.md)** — When understanding the test environment: container layout, startup sequence, parallel execution, HA image override
- **[Writing Tests](writing-tests.md)** — When writing tests: basic patterns, time-based tests, calling actions, polling
- **[Persistent Entities](persistent-entities.md)** — When you need entities available across multiple tests: YAML configuration, startup behavior, comparison with per-test entities
- **[Best Practices](best-practices.md)** — When optimizing test patterns: cleanup strategies, factory fixtures, area/label testing, time machine isolation
- **[Fixtures Reference](fixtures.md)** — When understanding available fixtures: docker, home_assistant, app_daemon, time_machine
- **[Troubleshooting](troubleshooting.md)** — When encountering issues: common errors, debugging tips
