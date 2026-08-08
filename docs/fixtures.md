# Available Fixtures

The harness provides four pytest fixtures that are automatically available when the package is installed.

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

## `home_assistant` (session scope)

Home Assistant API client with automatic authentication and retry logic.

### home_assistant API

```python
home_assistant.set_state(entity_id: str, state: str, attributes: dict = None) -> None
home_assistant.get_state(entity_id: str) -> dict
home_assistant.get_config() -> dict
home_assistant.assert_entity_state(entity_id: str, expected_state: str | Callable[[str], bool] | None = None, expected_attributes: dict = None, timeout: int = 5) -> None
home_assistant.remove_entity(entity_id: str) -> None
home_assistant.given_an_entity(entity_id: str, state: str, attributes: dict = None) -> None
home_assistant.given_entity_has(entity_id: str, area: str | None = ..., labels: list[str] | None = ...) -> None
home_assistant.clean_up_test_entities() -> None
home_assistant.restore_entity_config() -> None
home_assistant.call_action(domain: str, action: str, data: dict = None) -> None
```

### home_assistant Usage

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

#### Alternative: Manual cleanup

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

### home_assistant Methods

#### `set_state(entity_id, state, attributes=None)`

Sets the state of an entity.

- If the entity was created in the current test via `given_an_entity()`, the update is routed through the
  bundled `ha_test_harness` integration via WebSocket, which preserves its entity registry registration.
- Otherwise, the state is injected directly via the REST API (`POST /api/states`). REST-injected entities
  are written only to the HA state machine — they are **not** registered in the entity registry and cannot
  be used with `given_entity_has()`.

- **entity_id**: Entity ID (e.g., `"switch.test"`)
- **state**: State value (e.g., `"on"`, `"off"`, `"20.5"`)
- **attributes**: Optional dictionary of entity attributes

#### `get_state(entity_id)`

Returns entity state as a dictionary with `state`, `attributes`, `last_changed`, etc.

#### `get_config()`

Returns the Home Assistant configuration as a dictionary (from `GET /api/config`). Useful for
reading runtime settings such as the configured timezone (`time_zone`), `latitude`, `longitude`,
and `unit_system`. The `time_machine` fixture calls this automatically at session startup to
determine the timezone for `jump_to_next` local-time conversions.

#### `assert_entity_state(entity_id, expected_state=None, expected_attributes=None, timeout=5)`

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
# 1. Assert state only (existing behaviour)
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

#### `remove_entity(entity_id)`

Removes an entity from Home Assistant.

- If the entity was created via `given_an_entity()`, it is removed via the `ha_test_harness` integration
  WebSocket command, which deletes the entity from both the state machine and the entity registry.
  This is idempotent — if the entity is not found the command still succeeds.
- Otherwise, the entity is removed via the REST API, which removes it from the state machine only.

#### `given_an_entity(entity_id, state, attributes=None)`

Creates a fully-registered entity for testing with **automatic cleanup**.

Unlike `set_state()`, `given_an_entity()` creates the entity via the bundled `ha_test_harness` custom
integration. The entity is registered in the HA entity registry (it has a `unique_id`), appears in the HA UI,
and supports area/label assignment via `given_entity_has()`. The entity is tracked and automatically removed
after the test function completes.

Supported domains: `sensor`, `binary_sensor`, `switch`, `light`, `media_player`, `select`.

- **entity_id**: Entity ID (e.g., `"sensor.test_temp"`). The domain prefix must be one of the supported domains listed above.
- **state**: Initial state value (e.g., `"on"`, `"off"`, `"20.5"`)
- **attributes**: Optional dictionary of entity attributes

If called multiple times with the same `entity_id`, the entity's state is updated in place — it is tracked only once.

**Basic example:**

```python
def test_automation(home_assistant):
    home_assistant.given_an_entity("sensor.test", "42", {"unit_of_measurement": "°C"})
    assert home_assistant.get_state("sensor.test")["state"] == "42"
    # No cleanup needed - handled automatically!
```

**Combined with `given_entity_has()` (registry-only, not possible with `set_state()`):**

```python
def test_area_label_on_per_test_entity(home_assistant):
    home_assistant.given_an_entity("light.test_light", "off")
    home_assistant.given_entity_has("light.test_light", area="living_room", labels=["night_mode"])

    # Entity exists, is registered, and has area/label assigned
    assert home_assistant.get_state("light.test_light") is not None
    # Both entity and entity config are automatically cleaned up after the test
```

#### `clean_up_test_entities()`

Removes all entities created via `given_an_entity()`. This method is called automatically by the test harness after each test function, so you typically don't need to call it manually.

If cleanup fails for some entities, all tracked entities are still removed from tracking, and errors are reported collectively.

#### `given_entity_has(entity_id, area=..., labels=...)`

Assigns an area and/or labels to an entity via the Home Assistant entity registry, with **automatic rollback** at the end of the test function.
The entity's original area and labels are captured before any changes are made, so they can be restored by the harness after the test.

At least one of `area` or `labels` must be supplied. Each parameter is applied independently — omitting one leaves the corresponding field unchanged on the entity.

If the specified area does not yet exist in the Home Assistant area registry, it is **created automatically** before assigning it to the entity.
Likewise, any label IDs that do not yet exist in the label registry are **created automatically**.
Areas and labels created this way are not removed after each test — they persist for the lifetime of the test session.

> **When is registry creation required?**
> Automations that target entities using Jinja template functions such as `area_entities()` or `label_entities()` query the area/label registries at
> runtime, so the area or label must exist as a registry entry for these functions to return results.
> By contrast, automations that reference an area or label directly in the action `target` (e.g. `target: { area_id: living_room }`) resolve the
> assignment from the entity registry alone and do not require a matching area/label registry entry.
> `given_entity_has()` creates registry entries regardless, ensuring both targeting styles work.

- **entity_id**: Entity ID of an entity in the HA entity registry. This includes both persistent entities
  (defined in `ha_persistent_entities_path`) and per-test entities created via `given_an_entity()`.
  Entities created via `set_state()` are **not** registered and cannot be used here.
- **area**: Area ID to assign to the entity (e.g., `"living_room"`), `None` to remove any existing area assignment, or omit to leave the area unchanged.
  The area is created in the area registry if it does not already exist.
- **labels**: List of label IDs to assign to the entity. Replaces any existing labels. Pass `None` to remove all labels, or omit to leave labels unchanged.
  Any label IDs that do not already exist in the label registry are created automatically.

If called multiple times with the same `entity_id`, only the config captured on the first call is saved for restoration
(so the original pre-test area and labels are always what gets restored, regardless of how many times you update them during the test).

**Examples:**

```python
def test_area_based_automation(home_assistant):
    # Assign an area — original area is saved automatically
    home_assistant.given_entity_has("light.living_room", area="living_room")

    # Area is automatically restored to its original value after this test

def test_label_based_automation(home_assistant):
    # Assign a label — original labels are saved automatically
    home_assistant.given_entity_has("light.living_room", labels=["night_mode"])

    # Labels are automatically restored to original values after this test

def test_area_and_labels(home_assistant):
    # Assign both area and labels at once
    home_assistant.given_entity_has("light.living_room", area="living_room", labels=["night_mode"])

    # Both are automatically restored after this test
```

#### `restore_entity_config()`

Restores all entity area assignments and labels modified by `given_entity_has()` to the values they had before the test.
This method is called automatically by the test harness after each test function, so you typically don't need to call it manually.

If restoration fails for some entities, errors are reported collectively.

#### `call_action(domain, action, data=None)`

Calls a Home Assistant action (service). This is the standard way to trigger entity behaviour in Home Assistant — for example turning a light on or off —
and is preferred over `set_state()` for entities whose state is derived from other entities.

- **domain**: The service domain (e.g., `"light"`, `"switch"`, `"input_boolean"`)
- **action**: The action to call (e.g., `"turn_on"`, `"turn_off"`, `"toggle"`)
- **data**: Optional dictionary of action data (e.g., `{"entity_id": "light.living_room"}`)

> **Important:** For entities whose state is computed from another entity (e.g., a template `light` whose value is derived from an `input_boolean`), you must call
> the appropriate action rather than using `set_state()`. Directly setting the state of the derived entity will have no effect because Home Assistant will
> recompute it from the source entity. See [Writing Tests](usage.md#calling-actions) for more detail.

**Example:**

```python
def test_turn_on_light_via_action(home_assistant):
    # Turn on a light via action (preferred approach)
    home_assistant.call_action("light", "turn_on", {"entity_id": "light.living_room"})

    home_assistant.assert_entity_state("light.living_room", "on", timeout=5)
```

## `app_daemon` (session scope)

AppDaemon API client.

### app_daemon API

Currently provides basic initialization. Future versions will add methods for interacting with AppDaemon apps.

```python
def test_appdaemon(app_daemon):
    # Access base URL
    print(app_daemon.base_url)
```

## `time_machine` (session scope)

Manages time manipulation for deterministic testing of time-based automations.

**IMPORTANT LIMITATION**: Time can only move forward, never backward. The fixture is session-scoped, meaning time persists
across all tests in the session and cannot be reset to real time or an earlier point. This is a fundamental constraint of the Home Assistant container.

### time_machine API

```python
time_machine.fast_forward(delta: timedelta) -> None
time_machine.jump_to_next(month=None, day=None, day_of_month=None, hour=None, minute=None, second=None) -> None
time_machine.advance_to_preset(preset: str, offset: Optional[timedelta] = None) -> None
```

### time_machine Usage

```python
from datetime import timedelta

def test_time_manipulation(home_assistant, time_machine):
    # Advance time by 5 days
    time_machine.fast_forward(timedelta(days=5))

    # Jump to next Monday at 10:00 AM
    time_machine.jump_to_next(day="Monday", hour=10, minute=0)

    # Advance to 30 minutes after next sunrise
    time_machine.advance_to_preset("sunrise", timedelta(minutes=30))

    # Verify time-based automation triggered
    home_assistant.assert_entity_state("light.scheduled", "on")

    # NOTE: Time cannot be reset - it persists for the entire test session
```

### time_machine Methods

#### `fast_forward(delta: timedelta)`

Advances time forward by the specified timedelta. The advancement is cumulative - calling this method multiple times will continue advancing from the current fake time.

**Parameters:**

- **delta**: A timedelta object specifying the amount of time to advance. Supports weeks, days, hours, minutes, seconds, and microseconds.

**Examples:**

```python
# Advance by 1 day
time_machine.fast_forward(timedelta(days=1))

# Advance by 1 hour and 30 minutes
time_machine.fast_forward(timedelta(hours=1, minutes=30))

# Advance by 2 weeks, 3 days, and 4 hours
time_machine.fast_forward(timedelta(weeks=2, days=3, hours=4))

# Advance by 30 seconds
time_machine.fast_forward(timedelta(seconds=30))
```

**Raises:**

- `ValueError`: If delta is negative (time can only move forward)
- `TimeMachineError`: If time manipulation fails

#### `jump_to_next(month=None, day=None, day_of_month=None, hour=None, minute=None, second=None)`

Jumps to the next occurrence of specified calendar constraints. Constraints are applied in a specific order:

1. **Month**: Advance to next occurrence of specified month
2. **Day of month**: Set the day of the month (may advance to next month if needed)
3. **Weekday**: Advance to next occurrence of specified weekday
4. **Time**: Set hour/minute/second (preserving unspecified components)

All parameters are optional. Unspecified time components (hour/minute/second) preserve their values from the current fake time.

**Timezone and DST behaviour:**

When the `time_machine` fixture is used through the harness, `hour`/`minute`/`second` are
automatically interpreted as **local wall-clock time** in the timezone configured in Home Assistant
(e.g. `Europe/London`). This means callers always reason in the same timezone as their automations,
regardless of whether DST is currently active — the harness converts local time to UTC internally.

DST transitions between the current fake time and the target are handled transparently:
`jump_to_next(hour=20, minute=30)` always lands on 20:30 local time, even if a clock change
occurs in between.

**DST edge cases:**

- **Non-existent hour** (spring-forward gap, e.g. `hour=1, minute=30` on the spring-forward date):
  raises `ValueError` with a clear message — those minutes simply do not exist in the local timezone
  on that date.
- **Ambiguous hour** (fall-back, e.g. `hour=1, minute=30` on the fall-back date, which occurs
  twice): the *next* upcoming occurrence is chosen — the first (DST) occurrence is preferred; if it
  has already passed, the second (standard-time) occurrence is used instead.

**Parameters:**

- **month**: Month name ("Jan"/"January") or 3-char abbreviation (case-insensitive)
- **day**: Weekday name ("Mon"/"Monday") or 3-char abbreviation (case-insensitive)
- **day_of_month**: Day of the month (1-31). Applied after month, before weekday
- **hour**: Hour of day (0-23), in local timezone. Preserves current hour if omitted
- **minute**: Minute (0-59), in local timezone. Preserves current minute if omitted
- **second**: Second (0-59), in local timezone. Preserves current second if omitted

**Examples:**

```python
# Jump to next Monday at current time
time_machine.jump_to_next(day="Monday")

# Jump to next February, preserving current day and time
time_machine.jump_to_next(month="Feb")

# Jump to 1st of next month
time_machine.jump_to_next(day_of_month=1)

# Complex: From Jan 31 14:30:00, jump to next Monday in February at 10:00:00
# Result: Feb 3 10:00:00 (1st of Feb is Sat, next Mon is 3rd, time set to 10:00)
time_machine.jump_to_next(month="Feb", day="Monday", hour=10)
```

**Constraint Resolution Order Example:**

From **Tue Jan 31 14:30:00**, calling:

```python
time_machine.jump_to_next(day_of_month=1, day="Monday", hour=10)
```

**Step-by-step execution:**

1. Set to **1st of next month** → **Feb 1 14:30:00** (Feb 1 is Saturday)
2. Advance to **next Monday** → **Feb 3 14:30:00**
3. Set **hour to 10** → **Feb 3 10:30:00** (minutes/seconds preserved)

**Another example** - From **Tue Jan 31 14:30:00**, calling:

```python
time_machine.jump_to_next(month="Feb", day_of_month=1, day="Monday")
```

**Step-by-step execution:**

1. Jump to **February** → **Feb 28 14:30:00** (or Feb 29 in leap year, same day-of-month as current)
2. Set to **1st** → **Mar 1 14:30:00** (Feb 1 is in the past, so next occurrence is March 1)
3. Advance to **next Monday** → **Mar 3 14:30:00** (if Mar 1 is Saturday)

**Raises:**

- `ValueError`: If month/day names are invalid, numeric values are out of range, or the requested hour does not exist in the configured timezone on the target date (spring-forward gap)
- `TimeMachineError`: If result would not be in the future or manipulation fails

#### `advance_to_preset(preset, offset=None)`

Advances time to the next sunrise or sunset, with optional offset. Uses the `sun.sun` entity from Home Assistant to determine sunrise/sunset times.

**Parameters:**

- **preset**: Either "sunrise" or "sunset" (case-insensitive)
- **offset**: Optional `timedelta` to add to the preset time (can be negative for "before")

**Examples:**

```python
# Advance to next sunrise
time_machine.advance_to_preset("sunrise")

# Advance to 30 minutes after next sunrise
time_machine.advance_to_preset("sunrise", timedelta(minutes=30))

# Advance to 1 hour before next sunset
time_machine.advance_to_preset("sunset", timedelta(hours=-1))
```

**Raises:**

- `ValueError`: If get_entity_state callback is not configured or preset is invalid
- `TimeMachineError`: If entity fetch fails, parsing fails, or result would not be in future

### Limitations and Considerations

#### Time Can Only Move Forward (Critical Limitation)

**You CANNOT move time backward or reset time to real time.** This is a fundamental constraint of the Home Assistant container.

```python
# ✅ Supported - advance forward
time_machine.fast_forward(timedelta(days=1))

# ✅ Supported - jump to next occurrence (always in future)
time_machine.jump_to_next(day="Monday")

# ❌ NOT SUPPORTED - cannot move time backward
# Once time has advanced, it CANNOT go back

# ❌ This will raise an error:
time_machine.fast_forward(timedelta(days=-1))  # Negative values not allowed

# ❌ There is NO way to reset time to real time or an earlier point
# No reset_time() method exists
```

#### Session-Scoped Fixture Means Persistent Time

The `time_machine` fixture is **session-scoped**, meaning time persists across all tests in the session. Tests must explicitly advance time to their desired starting conditions.

**Best practice:** Each test that uses time manipulation should explicitly set its initial time state:

```python
def test_morning_automation(home_assistant, time_machine):
    # Explicitly advance to desired starting time
    time_machine.jump_to_next(day="Monday", hour=7)

    # ... test logic ...

def test_evening_automation(home_assistant, time_machine):
    # This test runs AFTER test_morning_automation, so time is already
    # Monday 7:XX. We need to explicitly advance to evening:
    time_machine.jump_to_next(hour=19)  # 7 PM

    # ... test logic ...
```

#### Second-Level Granularity

Time manipulation works at second-level precision. Sub-second accuracy is not supported:

```python
# ✅ Supported
time_machine.fast_forward(timedelta(seconds=60))

# ⚠️ Fractional seconds are truncated
time_machine.fast_forward(timedelta(seconds=3, milliseconds=500))  # Can only advance by whole seconds
```

#### Timezone Mirrors Home Assistant Configuration

The `time_machine` fixture reads the configured timezone from Home Assistant (`GET /api/config`) at
session startup and uses it for all `jump_to_next` local-time conversions. You cannot change the
timezone during a test session — it is determined by the Home Assistant configuration and is fixed
for the lifetime of the session.

#### Shared Clock Across Containers

Both Home Assistant and AppDaemon share the same fake clock. You cannot set different times for
each container.

#### State Persistence Across Tests

The `docker`, `home_assistant`, and `app_daemon` fixtures are session-scoped, so entity states persist across tests. The `time_machine` fixture is also session-scoped,
so time persists and cannot be reset.

**Best practice:** Always explicitly set initial time at the start of tests that use time manipulation. Reset relevant entity states if needed:

```python
def test_automation_sequence(home_assistant, time_machine):
    # Set initial conditions
    time_machine.jump_to_next(day="Monday", hour=6, minute=0, second=0) # Start from known time
    home_assistant.set_state("input_boolean.test_mode", "off")

    # ... test logic ...
```

#### Real-Time Services May Behave Differently

Some Home Assistant integrations rely on real-time APIs (e.g., weather services, sun position
calculations). These may not respond correctly with a fake time set.

```python
from ha_integration_test_harness import HomeAssistant, TimeMachine

def test_heating_schedule(home_assistant: HomeAssistant, time_machine: TimeMachine):
    """Test that heating turns on at scheduled time and turns off after delay."""

    # Advance to Monday morning before heating schedule (6:00 AM)
    time_machine.jump_to_next(day="Monday", hour=6, minute=0, second=0)

    # Verify heating is off
    state = home_assistant.get_state("climate.thermostat")
    assert state["attributes"]["hvac_action"] == "off"

    # Advance to heating schedule start (7:00 AM)
    time_machine.fast_forward(timedelta(hours=1))

    # Verify heating turned on
    home_assistant.assert_entity_state("climate.thermostat", "heat", timeout=10)

    # Simulate someone leaving home
    home_assistant.set_state("person.homeowner", "not_home")

    # Verify heating turned off (automation should detect absence)
    home_assistant.assert_entity_state("climate.thermostat", "off", timeout=5)

    # NOTE: Time remains at Monday 7:00 AM for subsequent test
```

All fixtures (`docker`, `home_assistant`, `app_daemon`, `time_machine`) are session-scoped:

- Created once when first test requests them
- Shared across all tests in the session
- Torn down after all tests complete
- Provides fast test execution (containers start once)
- **Time and entity states persist across tests**

**Important:** Because time persists and cannot be reset, time-dependent test scenarios should always explicitly set their initial time conditions.

## Next Steps

- Read [Troubleshooting](troubleshooting.md) for common issues
- See [Development Guide](development.md) for contributing
