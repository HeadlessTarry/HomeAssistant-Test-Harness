# Home Assistant Fixture

## `home_assistant` (session scope)

Home Assistant API client with automatic authentication and retry logic.

## API

```python
home_assistant.set_state(entity_id: str, state: str, attributes: dict = None) -> None
home_assistant.get_state(entity_id: str) -> dict
home_assistant.get_config() -> dict
home_assistant.assert_entity_state(entity_id: str, expected_state: str | Callable[[str], bool] | None = None, expected_attributes: dict = None, timeout: int = 5) -> None
home_assistant.remove_entity(entity_id: str) -> None
home_assistant.given_an_entity(entity_id: str, state: str) -> EntityBuilder
home_assistant.clean_up_test_entities() -> None
home_assistant.restore_entity_config() -> None
home_assistant.call_action(domain: str, action: str, data: dict = None) -> None
```

## Usage

```python
def test_home_assistant(home_assistant):
    # Create entity with automatic cleanup
    home_assistant.given_an_entity("switch.test", "on")

    # Get entity state
    state = home_assistant.get_state("switch.test")
    assert state["state"] == "on"

    # Poll until condition is met (with timeout)
    home_assistant.assert_entity_state("timer.test", "idle", timeout=30)

    # Entity is automatically cleaned up after test
```

### Alternative: Manual cleanup

```python
def test_manual_cleanup(home_assistant):
    # Set entity state (manual cleanup required)
    home_assistant.set_state("switch.test", "on")

    # Get entity state
    state = home_assistant.get_state("switch.test")
    assert state["state"] == "on"

    # Manual cleanup
    home_assistant.remove_entity("switch.test")
```

## Methods

### `set_state(entity_id, state, attributes=None)`

Sets the state of an entity.

- If the entity was created in the current test via `given_an_entity()`, the update is routed through the
  bundled `ha_test_harness` integration via WebSocket, which preserves its entity registry registration.
- Otherwise, the state is injected directly via the REST API (`POST /api/states`). REST-injected entities
  are written only to the HA state machine — they are **not** registered in the entity registry.

- **entity_id**: Entity ID (e.g., `"switch.test"`)
- **state**: State value (e.g., `"on"`, `"off"`, `"20.5"`)
- **attributes**: Optional dictionary of entity attributes

### `get_state(entity_id)`

Returns entity state as a dictionary with `state`, `attributes`, `last_changed`, etc.

### `get_config()`

Returns the Home Assistant configuration as a dictionary (from `GET /api/config`). Useful for
reading runtime settings such as the configured timezone (`time_zone`), `latitude`, `longitude`,
and `unit_system`. The `time_machine` fixture calls this automatically at session startup to
determine the timezone for `jump_to_next` local-time conversions.

### `assert_entity_state(entity_id, expected_state=None, expected_attributes=None, timeout=5)`

Polls entity state and/or attributes until all conditions are met, or the timeout expires. Raises `AssertionError` if the timeout occurs.
At least one of `expected_state` or `expected_attributes` must be provided.

- **entity_id**: Entity ID (e.g., `"switch.test"`)
- **expected_state**: State value to match exactly (e.g., `"on"`), or a callable predicate that receives the current state string and returns `True` when satisfied.
  Pass `None` (or omit) to skip state checking.
- **timeout**: Maximum seconds to wait (default: 5)
- **expected_attributes**: Optional dictionary of attribute names to expected values. Each value may be an exact value (compared with `==`) or a callable predicate
  that receives the actual attribute value and returns `True` when satisfied. Only the attributes listed here are checked; additional attributes on the entity are ignored.

**Examples:**

```python
# 1. Assert state only
home_assistant.assert_entity_state("switch.test", "on", timeout=10)

# 2. Assert state and attributes
home_assistant.assert_entity_state(
    "light.living_room",
    "on",
    expected_attributes={"brightness": 255, "color_temp": 300},
)

# 3. Assert attributes only (no state check)
home_assistant.assert_entity_state(
    "climate.thermostat",
    expected_attributes={"hvac_action": "heating"},
    timeout=10,
)

# 4. Assert attribute using a lambda predicate
home_assistant.assert_entity_state(
    "sensor.temperature",
    expected_attributes={"unit_of_measurement": lambda u: u in ("°C", "°F")},
)

# 5. Assert multiple attributes
home_assistant.assert_entity_state(
    "media_player.living_room",
    "playing",
    expected_attributes={
        "volume_level": lambda v: v > 0.1,
        "media_title": "My Song",
    },
    timeout=15,
)
```

### `remove_entity(entity_id)`

Removes an entity from Home Assistant.

- If the entity was created via `given_an_entity()`, it is removed via the `ha_test_harness` integration
  WebSocket command, which deletes the entity from both the state machine and the entity registry.
  This is idempotent — if the entity is not found the command still succeeds.
- Otherwise, the entity is removed via the REST API, which removes it from the state machine only.

### `given_an_entity(entity_id, state) -> EntityBuilder`

Creates a fully-registered entity for testing with **automatic cleanup**.

Unlike `set_state()`, `given_an_entity()` creates the entity via the bundled `ha_test_harness` custom
integration. The entity is registered in the HA entity registry (it has a `unique_id`), appears in the HA UI,
and supports area/label assignment via the returned builder. The entity is tracked and automatically removed
after the test function completes.

Supported domains: `sensor`, `binary_sensor`, `switch`, `light`, `media_player`, `select`.

- **entity_id**: Entity ID (e.g., `"sensor.test_temp"`). The domain prefix must be one of the supported domains listed above.
- **state**: Initial state value (e.g., `"on"`, `"off"`, `"20.5"`)

Returns an `EntityBuilder` for fluent configuration. See [EntityBuilder](#entitybuilder) below.

If called multiple times with the same `entity_id`, the entity's state is updated in place — it is tracked only once.

**Basic example:**

```python
def test_automation(home_assistant):
    home_assistant.given_an_entity("sensor.test", "42")
    assert home_assistant.get_state("sensor.test")["state"] == "42"
    # No cleanup needed - handled automatically!
```

**With builder chaining:**

```python
def test_area_label_on_per_test_entity(home_assistant):
    home_assistant.given_an_entity("light.test_light", "off") \
        .in_area("living_room") \
        .with_labels(["night_mode"]) \
        .with_attributes({"brightness": 200})

    # Entity exists, is registered, and has area/label assigned
    assert home_assistant.get_state("light.test_light") is not None
    # Both entity and entity config are automatically cleaned up after the test
```

### `clean_up_test_entities()`

Removes all entities created via `given_an_entity()`. This method is called automatically by the test harness after each test function, so you typically don't need to call it manually.

If cleanup fails for some entities, all tracked entities are still removed from tracking, and errors are reported collectively.

### `restore_entity_config()`

Restores all entity area assignments and labels modified by the builder's `in_area()` and `with_labels()` methods to the values they had before the test.
This method is called automatically by the test harness after each test function, so you typically don't need to call it manually.

If restoration fails for some entities, errors are reported collectively.

### `call_action(domain, action, data=None)`

Calls a Home Assistant action (service). This is the standard way to trigger entity behaviour in Home Assistant — for example turning a light on or off —
and is preferred over `set_state()` for entities whose state is derived from other entities.

- **domain**: The service domain (e.g., `"light"`, `"switch"`, `"input_boolean"`)
- **action**: The action to call (e.g., `"turn_on"`, `"turn_off"`, `"toggle"`)
- **data**: Optional dictionary of action data (e.g., `{"entity_id": "light.living_room"}`)

> **Important:** For entities whose state is computed from another entity (e.g., a template `light` whose value is derived from an `input_boolean`), you must call
> the appropriate action rather than using `set_state()`. Directly setting the state of the derived entity will have no effect because Home Assistant will
> recompute it from the source entity. See [Writing Tests](writing-tests.md#calling-actions) for more detail.

**Example:**

```python
def test_turn_on_light_via_action(home_assistant):
    # Turn on a light via action (preferred approach)
    home_assistant.call_action("light", "turn_on", {"entity_id": "light.living_room"})

    home_assistant.assert_entity_state("light.living_room", "on", timeout=5)
```

## EntityBuilder

The `EntityBuilder` provides a fluent, chainable API for configuring virtual entities after creation.

### Builder Methods

#### `in_area(area: str) -> Self`

Assigns the entity to an area. Creates the area in the area registry if it doesn't exist.

```python
home_assistant.given_an_entity("light.test", "off").in_area("living_room")
```

#### `with_labels(labels: list[str]) -> Self`

Assigns labels to the entity. Creates any missing labels in the label registry.

```python
home_assistant.given_an_entity("light.test", "off").with_labels(["night_mode", "security"])
```

#### `with_device_class(device_class: str) -> Self`

Sets the device_class attribute for the entity.

```python
home_assistant.given_an_entity("binary_sensor.test", "off").with_device_class("motion")
```

#### `with_attributes(attributes: dict) -> Self`

Sets custom attributes for the entity. Successive calls merge attributes.

```python
home_assistant.given_an_entity("sensor.test", "20").with_attributes({
    "unit_of_measurement": "°C",
    "device_class": "temperature"
})
```

### Chaining Example

```python
def test_complex_entity(home_assistant):
    home_assistant.given_an_entity("light.living_room", "off") \
        .in_area("living_room") \
        .with_labels(["night_mode"]) \
        .with_device_class("light") \
        .with_attributes({"brightness": 200, "color_temp": 300})

    # Entity is fully configured and will be cleaned up automatically
```
