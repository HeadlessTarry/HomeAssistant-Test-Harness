# Writing Tests

## Overview

Tests run against real Home Assistant and AppDaemon instances, not mocks. This ensures your configuration works correctly in an environment that mirrors production.

## Basic Test

```python
def test_entity_state(home_assistant):
    """Test setting and reading entity states with automatic cleanup."""
    home_assistant.given_an_entity("input_boolean.test", "on")

    state = home_assistant.get_state("input_boolean.test")
    assert state["state"] == "on"

    # Entity is automatically cleaned up after test
```

## Time-Based Test

```python
def test_scheduled_automation(home_assistant, time_machine):
    """Test automation that triggers at specific time."""
    # Jump to next Monday at 10:00 AM
    time_machine.jump_to_next(day="Monday", hour=10, minute=0)

    # Verify automation triggered
    home_assistant.assert_entity_state("light.morning", "on", timeout=5)
```

## Calling Actions

Use `call_action()` to trigger Home Assistant actions (services) from your tests. This is the standard way to interact with entities in Home Assistant
and should be preferred over `set_state()` in most cases:

```python
def test_turn_on_light_via_action(home_assistant):
    """Test controlling a light via an action."""
    home_assistant.call_action("light", "turn_on", {"entity_id": "light.living_room"})

    home_assistant.assert_entity_state("light.living_room", "on", timeout=5)
```

### Actions vs. `set_state()`: Template Entities

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

## Polling for State Changes

```python
def test_polling_with_assert(home_assistant):
    """Test automation that has a delay."""
    # set_state() injects state via REST (unregistered entity — not in the entity registry).
    # Use given_an_entity() instead if you also need area/label assignment.
    home_assistant.set_state("binary_sensor.motion", "on")

    # Poll until light turns on (or timeout after 30 seconds)
    home_assistant.assert_entity_state("light.living_room", "on", timeout=30)
```

## Next Steps

- [Persistent Entities](persistent-entities.md) — When you need entities available across multiple tests
- [Best Practices](best-practices.md) — Cleanup patterns, factory fixtures, area/label testing
- [Time Machine Fixture](time-machine-fixture.md) — When testing time-based automations
