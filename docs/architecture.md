# Architecture

## Overview

Integration tests use a Docker Compose environment to run isolated instances of Home Assistant and AppDaemon.

## Container Architecture

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  Test Suite (pytest)                                        │
│  ├── Uses harness package (DockerComposeManager,            │
│  │   HomeAssistant, AppDaemon, TimeMachine)                 │
│  └── Interacts via HTTP/WebSocket APIs                      │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose Environment                                 │
│  ┌────────────────────────┐   ┌──────────────────────────┐  │
│  │  Home Assistant        │   │  AppDaemon               │  │
│  │  Port: 8123 (ephemeral)│   │  Port: 5050 (ephemeral)  │  │
│  │  ├── Configuration     │   │  ├── Apps                │  │
│  │  │   (from repo)       │   │  │   (from repo)         │  │
│  │  │   ├── Automations   │   │  ├── Connected to HA     │  │
│  │  │   ├── Scripts       │   │  └── API enabled         │  │
│  │  │   └── Templates     │   │                          │  │
│  │  └── ha_test_harness   │   │                          │  │
│  │      (custom component)│   │                          │  │
│  └────────────────────────┘   └──────────────────────────┘  │
│             │                              │                │
│             └──────────┬───────────────────┘                │
│                        ▼                                    │
│              ┌──────────────────┐                           │
│              │  Shared Volume   │                           │
│              │  - Auth token    │                           │
│              │  - Ready flags   │                           │
│              └──────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

The `ha_test_harness` custom component is deployed into the Home Assistant instance to enable
the test fixtures to interact with HA over WebSocket commands for entity registration and management.

## Startup Sequence

The `docker-compose.yaml` orchestrates container startup with dependencies and health checks:

1. **Home Assistant starts** (`containers/homeassistant/entrypoint.sh`):
   - Copies repository configuration into `/config`
   - Starts Home Assistant server
   - Completes onboarding (creates test user)
   - Generates long-lived access token
   - Writes token to shared volume (`/shared_data/.ha_token`)
   - Creates ready flag (`/shared_data/.homeassistant_ready`)

2. **AppDaemon starts** (after HA is healthy) (`containers/appdaemon/entrypoint.sh`):
   - Waits for HA token file
   - Reads HA long-lived access token from shared volume
   - Generates `appdaemon.yaml` from template with token
   - Starts AppDaemon server
   - Waits for initialization to complete
   - Creates ready flag (`/shared_data/.appdaemon_ready`)

3. **Docker Compose health checks**:
   - Home Assistant: checks for `.homeassistant_ready` flag
   - AppDaemon: checks for `.appdaemon_ready` flag
   - `docker compose up --wait` blocks until both are healthy

## Parallel Test Execution

The environment supports **parallel test runs** via Docker Compose project names:

- Each test session gets a unique project ID (`uuid.uuid4().hex`)
- Containers are named `<project_id>-<service>-1` (e.g., `a1b2c3d4-homeassistant-1`)
- Ports are dynamically assigned (ephemeral mapping)
- Volumes are project-scoped (isolated state per run)

This design allows multiple developers or CI jobs to run tests simultaneously without conflicts.

## Home Assistant Image Override

By default, the test harness uses the `homeassistant/home-assistant:stable` Docker image.
You can override this to test against a specific Home Assistant version (e.g. a beta or
release candidate) before `stable` catches up.

### Override Methods

Three methods are supported, in priority order:

#### 1. Environment Variable

Set `HA_IMAGE` before running tests:

```bash
export HA_IMAGE="homeassistant/home-assistant:2026.7"
pytest
```

#### 2. pytest Configuration

Add `ha_image` to your `pyproject.toml`:

```toml
[tool.pytest.ini_options]
ha_image = "homeassistant/home-assistant:2026.7"
```

#### 3. Fixture Override

Override the `ha_image` fixture in your `conftest.py`:

```python
import pytest

@pytest.fixture(scope="session")
def ha_image():
    return "homeassistant/home-assistant:2026.7"
```

### Priority

When multiple methods are used, the priority order is:

1. Environment variable (`HA_IMAGE`) — highest
2. pytest configuration (`ha_image`)
3. Fixture override (the fixture checks env var and config, so overriding the fixture itself gives full control)
4. Default from `docker-compose.yaml` (`homeassistant/home-assistant:stable`) — lowest

### Example Use Case

Testing against a beta version before it reaches `stable`:

```bash
# Test against the 2026.7 beta
HA_IMAGE="homeassistant/home-assistant:2026.7b0" pytest
```
