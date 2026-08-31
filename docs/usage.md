# Usage Guide

## Overview

The integration test harness provides a complete Docker-based test environment for
Home Assistant and AppDaemon. Tests run against real instances, not mocks, ensuring
your configuration works correctly.

## Installation

See [Installation Guide](installation.md) for details.

## How It Works

### Auto-Discovery

When you run tests, the harness:

1. **Checks environment variables**: Looks for `HOME_ASSISTANT_CONFIG_ROOT` (Home Assistant) and `APPDAEMON_CONFIG_ROOT` (AppDaemon)
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
export HOME_ASSISTANT_CONFIG_ROOT=/path/to/homeassistant/config
export APPDAEMON_CONFIG_ROOT=/path/to/appdaemon/config
pytest
```

If neither environment variables are set nor the default subdirectories exist, configuration validation will fail.

### Container Lifecycle

- **Session-scoped**: Containers start once per test session and are shared across all tests
- **Automatic cleanup**: Containers are stopped and removed after all tests complete
- **Parallel-safe**: Dynamic port allocation allows multiple test runs concurrently

## Test Environment Architecture

Integration tests use a Docker Compose environment to run isolated instances of Home Assistant and AppDaemon.

### Container Architecture

```plaintext
┌─────────────────────────────────────────────────────────────┐
│  Test Suite (pytest)                                        │
│  ├── Uses harness package (DockerComposeManager,            │
│  │   HomeAssistant, AppDaemon, TimeMachine)                 │
│  └── Interacts via HTTP APIs                                │
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
│  │  ├── Automations       │   │  ├── Connected to HA     │  │
│  │  ├── Scripts           │   │  └── API enabled         │  │
│  │  └── Templates         │   │                          │  │
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

### Startup Sequence

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

### Parallel Test Execution

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

## Writing Tests

### Basic Test

```python
def test_entity_state(home_assistant):
    """Test setting and reading entity states with automatic cleanup."""
    home_assistant.given_an_entity("input_boolean.test", "on")

    state = home_assistant.get_state("input_boolean.test")
    assert state["state"] == "on"

    # Entity is automatically cleaned up after test
```

### Time-Based Test

```python
def test_scheduled_automation(home_assistant, time_machine):
    """Test automation that triggers at specific time."""
    # Jump to next Monday at 10:00 AM
    time_machine.jump_to_next(day="Monday", hour=10, minute=0)

    # Verify automation triggered
    home_assistant.assert_entity_state("light.morning", "on", timeout=5)
```

### Calling Actions

Use `call_action()` to trigger Home Assistant actions (services) from your tests. This is the standard way to interact with entities in Home Assistant
and should be preferred over `set_state()` in most cases:

```python
def test_turn_on_light_via_action(home_assistant):
    """Test controlling a light via an action."""
    home_assistant.call_action("light", "turn_on", {"entity_id": "light.living_room"})

    home_assistant.assert_entity_state("light.living_room", "on", timeout=5)
```

#### Actions vs. `set_state()`: Template Entities

For entities whose state is **derived from another entity** (e.g., a template `light` backed by an `input_boolean`), you **must** call the appropriate
action rather than setting the state directly. Calling `set_state()` on the derived entity has no effect because Home Assistant recomputes its state from
the source entity.

For example, given this configuration:

```yaml
input_boolean:
  state_living_room_floor_lamp:
    name: "[State] Living Room Floor Lamp"

light:
  - platform: template
    lights:
      living_room_floor_lamp:
        value_template: "{{ is_state('input_boolean.state_living_room_floor_lamp', 'on') }}"
        turn_on:
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.state_living_room_floor_lamp
        turn_off:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.state_living_room_floor_lamp
```

**Wrong** — this has no effect because `light.living_room_floor_lamp` is computed from the input_boolean:

```python
home_assistant.set_state("light.living_room_floor_lamp", "on")  # ❌ Does nothing
```

**Correct** — call the action on the light entity, which triggers the underlying `input_boolean` update:

```python
home_assistant.call_action("light", "turn_on", {"entity_id": "light.living_room_floor_lamp"})  # ✅
```

### Polling for State Changes

```python
def test_polling_with_assert(home_assistant):
    """Test automation that has a delay."""
    # set_state() injects state via REST (unregistered entity — not in the entity registry).
    # Use given_an_entity() instead if you also need area/label assignment.
    home_assistant.set_state("binary_sensor.motion", "on")

    # Poll until light turns on (or timeout after 30 seconds)
    home_assistant.assert_entity_state("light.living_room", "on", timeout=30)
```

## Persistent Session Entities

### About Persistent Entities

Home Assistant integrations often create entities dynamically at runtime — sensors from MQTT,
climate devices from Z-Wave, media players from Sonos, etc. These integration-created entities are
not typically defined in `configuration.yaml`, but your automations and scripts can depend on them.

The harness supports **persistent session entities**: a YAML file of entity definitions that are
registered with the test instance of Home Assistant during container startup. Unlike per-test
entities created via `given_an_entity()`, persistent entities simulate real integration-created
entities and are never automatically removed between tests.

### When to Use Persistent Entities

Use persistent entities when:

- Your automations/scripts reference entities created by integrations (e.g., `light.bedroom` from a Zigbee integration)
- You need consistent, reliable entity references across multiple tests
- You want to avoid setting up the same entities in every test function
- Tests fail because Home Assistant doesn't recognize services (e.g., `light.turn_on`) due to missing domain entities

**Example scenario:**

```yaml
# Your automation in configuration.yaml
automation:
  - id: sunset_lights
    alias: Sunset - Turn on lights
    trigger:
      platform: sun
      event: sunset
    action:
      - action: light.turn_on
        target:
          entity_id:
            - light.bedroom
            - light.living_room
```

To test this automation, you need `light.bedroom` and `light.living_room` to exist. Rather than creating them in every test with `given_an_entity()`, define them once in a persistent entities file.

### Configuration

Create a YAML file with your persistent entity definitions:

```yaml
# persistent_entities.yaml
input_boolean:
  guest_mode:
    name: "Guest Mode"
    initial: false
  # Backing state helpers used by the template entities defined below.
  # In this testing pattern, template entities that should have a controllable,
  # persistent on/off state use a separate helper entity to store and manage that
  # state. The turn_on/turn_off actions on the template entity update the helper so
  # that the template reflects the change in tests.
  state_living_room_lamp:
    name: "[State] Living Room Lamp"
    initial: false
  state_garage_door:
    name: "[State] Garage Door"
    initial: false

input_number:
  temperature:
    name: "Target Temperature"
    initial: 20
    min: 10
    max: 30

template:
  - light:
      - name: "Living Room Lamp"
        unique_id: "living_room_lamp"
        state: "{{ is_state('input_boolean.state_living_room_lamp', 'on') }}"
        turn_on:
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.state_living_room_lamp
        turn_off:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.state_living_room_lamp
  - switch:
      - name: "Garage Door"
        unique_id: "garage_door"
        state: "{{ is_state('input_boolean.state_garage_door', 'on') }}"
        turn_on:
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.state_garage_door
        turn_off:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.state_garage_door
```

Then reference the YAML file in your pytest configuration:

```toml
[tool.pytest.ini_options]
ha_persistent_entities_path = "persistent_entities.yaml"
```

### YAML Format

Define entities by domain using standard [Home Assistant Packages](https://www.home-assistant.io/docs/configuration/packages/) structure.
Any domain/entity configuration that Home Assistant supports can be included. During startup,
the test harness copies your persistent entities file into a staged configuration directory under a
unique generated filename (e.g. `_harness_persistent_entities_<uuid>.yaml`), then patches
`configuration.yaml` in that staged directory to reference the generated filename:

```yaml
homeassistant:
  packages:
    test_harness: !include _harness_persistent_entities_<uuid>.yaml
```

The `!include` path in `configuration.yaml` will reference the staged filename, **not** the original basename
you specified in `ha_persistent_entities_path`. This is expected behavior - if you inspect the staged
`configuration.yaml` while troubleshooting, you will see the generated name rather than your original filename.

This keeps your existing configuration intact while loading persistent entities from a separate file.

For template entities, prefer modern `template:` blocks with `unique_id` fields instead of legacy
`platform: template` syntax, so Home Assistant registers the entities in the entity registry.
This is required for any test that uses `home_assistant.given_entity_has(...)`, which interacts with the entity registry.

### Startup Behavior

When `ha_persistent_entities_path` is configured:

1. **At initialization**: The harness validates the YAML file
2. **At container startup**:
  - Creates a temporary copy of your Home Assistant configuration directory
  - Copies the persistent entities YAML file into the staged config under a unique generated name
    (e.g. `_harness_persistent_entities_<uuid>.yaml`) to avoid conflicts with any existing files
  - Patches `configuration.yaml` in the staged config to append `homeassistant.packages.test_harness`
    with an `!include` pointing to the generated filename
  - Starts Home Assistant with the staged configuration
3. **Your original config is never modified** - staging ensures isolation
4. **Entities are registered during HA startup**, so all domain services are properly initialized

### Example Test

```python
def test_sunset_automation(home_assistant, time_machine):
    """Test the sunset automation with persistent entities.

    Assumes light.bedroom and light.living_room are defined in
    persistent_entities.yaml
    """
    # Entities are already registered and available at test start
    assert home_assistant.get_state("light.bedroom")["state"] == "off"
    assert home_assistant.get_state("light.living_room")["state"] == "off"

    # Advance time to sunset
    time_machine.advance_to_preset("sunset", offset=timedelta(minutes=1))

    # Verify automation triggered both lights
    home_assistant.assert_entity_state("light.bedroom", "on", timeout=5)
    home_assistant.assert_entity_state("light.living_room", "on", timeout=5)
```

### Comparison: Per-Test vs. Persistent

| Feature | Per-Test (`given_an_entity`) | Persistent (YAML file) |
|---------|------------------------------|------------------------|
| Creation | During test via Python | At container startup |
| Scope | Single test function | Entire session |
| Cleanup | Automatic after test | Never (session lifetime) |
| Entity registry | Yes — has `unique_id`, visible in UI | Yes |
| Area / label assignment | Yes (`given_entity_has()`) | Yes (`given_entity_has()`) |
| Domain service calls | Yes (`turn_on`, `turn_off`, etc.) | Yes |
| Use case | Temporary test-specific data | Integration-created entities |

## Best Practices

### Cleanup

The harness provides **automatic cleanup** for test entities via `given_an_entity()`:

```python
def test_with_auto_cleanup(home_assistant):
    """Entities created with given_an_entity are automatically cleaned up."""
    home_assistant.given_an_entity("switch.test", "on")

    # ... test logic ...

    # No cleanup needed - handled automatically!
```

**Manual cleanup** is still supported for cases where you need explicit control:

```python
def test_with_manual_cleanup(home_assistant):
    """Manual cleanup when needed."""
    entity_id = "switch.test"
    home_assistant.set_state(entity_id, "on")

    # ... test logic ...

    # Manual cleanup
    home_assistant.remove_entity(entity_id)
```

**When to use each approach:**

- **Use `given_an_entity()`**: For most test entities. Entities are registered in the entity registry
  (have a `unique_id`), appear in the HA UI, respond to service calls (`turn_on`, `turn_off`), and can be
  combined with `given_entity_has()` for area/label assignment.
  Supported domains: `sensor`, `binary_sensor`, `switch`, `light`, `media_player`, `select`.
- **Use `set_state()`**: For raw state injection where registry registration is not needed — e.g. providing
  a synthetic sensor reading that an automation reads via a template. Entities created this way cannot be
  used with `given_entity_has()`.

### Factory Fixtures

Use factory patterns for creating multiple test entities with automatic cleanup:

```python
import pytest

@pytest.fixture
def create_entity(home_assistant):
    """Factory fixture with automatic cleanup via given_an_entity."""
    def _create(entity_id, state, **attributes):
        home_assistant.given_an_entity(entity_id, state, attributes)
        return entity_id

    return _create

def test_multiple_entities(create_entity):
    light1 = create_entity("light.test1", "on", brightness=255)
    light2 = create_entity("light.test2", "off")
    # Entities automatically cleaned up after test
```

**Alternative with manual tracking** (for advanced use cases):

```python
import pytest

@pytest.fixture
def create_entity_manual(home_assistant):
    """Factory fixture with manual cleanup tracking."""
    created = []

    def _create(entity_id, state):
        home_assistant.set_state(entity_id, state)
        created.append(entity_id)
        return entity_id

    yield _create

    # Manual cleanup
    for entity_id in created:
        home_assistant.remove_entity(entity_id)

def test_multiple_entities(create_entity_manual):
    light1 = create_entity_manual("light.test1", "on")
    light2 = create_entity_manual("light.test2", "off")
    # Entities cleaned up by fixture teardown
```

### Testing Area and Label Based Automations

Use `given_entity_has()` to temporarily assign an area or labels to an entity for the duration of a test.
The harness automatically creates any missing area or label registry entries and restores the entity's original configuration after the test.

`given_entity_has()` works with both persistent entities and per-test entities created via `given_an_entity()`.
This means you can create a test-specific entity and immediately assign it an area or label — all within a single test:

```python
def test_per_test_entity_with_area_and_label(home_assistant):
    # Create a per-test light entity (registered in the entity registry)
    home_assistant.given_an_entity("light.test_light", "off")

    # Assign area and label — works because given_an_entity() registers the entity
    home_assistant.given_entity_has("light.test_light", area="living_room", labels=["night_mode"])

    # Trigger automation targeting by label or area
    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.label_automation_trigger"})
    home_assistant.assert_entity_state("light.test_light", "on", timeout=10)
    # Entity and its config are both automatically cleaned up after the test
```

```python
def test_label_based_automation(home_assistant):
    # Assign the label — created in the label registry if it doesn't exist
    home_assistant.given_entity_has("light.living_room", labels=["night_mode"])

    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.label_automation_trigger"})
    home_assistant.assert_entity_state("light.living_room", "on", timeout=10)
    # Labels are automatically restored after this test

def test_area_based_automation(home_assistant):
    # Assign the area — created in the area registry if it doesn't exist
    home_assistant.given_entity_has("light.living_room", area="living_room")

    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.area_automation_trigger"})
    home_assistant.assert_entity_state("light.living_room", "on", timeout=10)
    # Area assignment is automatically restored after this test
```

#### Template Functions vs. Direct Targeting

Home Assistant automations can target entities by area or label in two ways, and the distinction matters for testing:

**Template functions** — `area_entities()` and `label_entities()` query the area/label registry at runtime:

```yaml
# automation in configuration.yaml
- action: light.turn_on
  target:
    entity_id: "{{ label_entities('night_mode') }}"
```

**Direct target keys** — `area_id:` and `label_id:` resolve the assignment from the entity registry alone:

```yaml
# automation in configuration.yaml
- action: light.turn_on
  target:
    label_id: night_mode
```

When using template functions (`area_entities()` / `label_entities()`), the area or label **must exist as a registry entry** for the function to return any results.
When using direct target keys (`area_id:` / `label_id:`), no registry entry is needed — Home Assistant resolves the assignment directly from the entity registry.

`given_entity_has()` creates the necessary registry entries for both cases, so your tests work regardless of which targeting style your automations use.

### Time Machine Isolation

Only request `time_machine` fixture in tests that need time manipulation:

```python
from datetime import timedelta

# Don't do this - time machine in every test
def test_normal(home_assistant, time_machine):
    pass

# Do this - only when needed
def test_time_based(home_assistant, time_machine):
    # Always explicitly set initial time conditions
    time_machine.fast_forward(timedelta(days=1))
    # ... test logic ...
```

**Important:** The `time_machine` fixture is session-scoped, so time persists across all tests and cannot be reset. Each test using time manipulation should
explicitly set its initial time state.

## Configuration Requirements

Your Home Assistant repository must contain:

- `configuration.yaml` at the root
- Valid Home Assistant configuration structure
- Any referenced files (automations, scripts, templates, etc.)

The harness mounts your entire repository, so all files are available to Home Assistant.

## Next Steps

- Review [Available Fixtures](fixtures.md) for complete API reference
- Check [Troubleshooting](troubleshooting.md) for common issues
