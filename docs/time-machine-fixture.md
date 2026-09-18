# Time Machine Fixture

## `time_machine` (session scope)

Manages time manipulation for deterministic testing of time-based automations.

**IMPORTANT LIMITATION**: Time can only move forward, never backward. The fixture is session-scoped, meaning time persists
across all tests in the session and cannot be reset to real time or an earlier point. This is a fundamental constraint of the Home Assistant container, which employs a monotonic clock.

## API

```python
time_machine.fast_forward(delta: timedelta) -> None
time_machine.jump_to_next(month=None, day=None, day_of_month=None, hour=None, minute=None, second=None) -> None
time_machine.advance_to_preset(preset: str, offset: Optional[timedelta] = None) -> None
```

## Usage

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

## Methods

### `fast_forward(delta: timedelta)`

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

### `jump_to_next(month=None, day=None, day_of_month=None, hour=None, minute=None, second=None)`

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

### `advance_to_preset(preset, offset=None)`

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

## Limitations and Considerations

### Time Can Only Move Forward (Critical Limitation)

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

### Session-Scoped Fixture Means Persistent Time

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

### Second-Level Granularity

Time manipulation works at second-level precision. Sub-second accuracy is not supported:

```python
# ✅ Supported
time_machine.fast_forward(timedelta(seconds=60))

# ⚠️ Fractional seconds are truncated
time_machine.fast_forward(timedelta(seconds=3, milliseconds=500))  # Can only advance by whole seconds
```

### Timezone Mirrors Home Assistant Configuration

The `time_machine` fixture reads the configured timezone from Home Assistant (`GET /api/config`) at
session startup and uses it for all `jump_to_next` local-time conversions. You cannot change the
timezone during a test session — it is determined by the Home Assistant configuration and is fixed
for the lifetime of the session.

### Shared Clock Across Containers

Both Home Assistant and AppDaemon share the same fake clock. You cannot set different times for
each container.

### State Persistence Across Tests

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

### Real-Time Services May Behave Differently

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

**Important:** Because time persists and cannot be reset, time-dependent test scenarios should always explicitly set their initial time conditions.
