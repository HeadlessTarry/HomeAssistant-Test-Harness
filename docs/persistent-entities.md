# Persistent Entities

## Overview

Home Assistant integrations often create entities dynamically at runtime — sensors from MQTT,
climate devices from Z-Wave, media players from Sonos, etc. These integration-created entities are
not typically defined in `configuration.yaml`, but your automations and scripts can depend on them.

The harness supports **persistent entities**: a YAML file of entity definitions that are
registered with the test instance of Home Assistant during container startup. Unlike per-test
entities created via `given_an_entity()`, persistent entities simulate real integration-created
entities and are never automatically removed between tests.

## When to Use Persistent Entities

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

## Configuration

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

## YAML Format

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

## Startup Behavior

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

## Example Test

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

## Comparison: Per-Test Entity vs. Persistent Entity

| Feature | Per-Test Entity (`given_an_entity`) | Persistent Entity (YAML file) |
|---------|------------------------------|------------------------|
| Creation | During test via Python | At container startup |
| Scope | Single test function | Entire session |
| Cleanup | Automatic after test | Never (session lifetime) |
| Entity registry | Yes — has `unique_id`, visible in UI | Yes |
| Area / label assignment | Yes (`given_entity_has()`) | Yes (`given_entity_has()`) |
| Domain service calls | Yes (`turn_on`, `turn_off`, etc.) | Yes |
| Use case | Temporary test-specific data | Integration-created entities |
