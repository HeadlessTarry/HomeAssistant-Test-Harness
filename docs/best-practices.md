# Best Practices

## Cleanup

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
  configured with area/label assignment via the builder pattern.
  Supported domains: `sensor`, `binary_sensor`, `switch`, `light`, `media_player`, `select`.
- **Use `set_state()`**: For raw state injection where registry registration is not needed — e.g. providing
  a synthetic sensor reading that an automation reads via a template. Entities created this way are not
  registered in the entity registry.

## Factory Fixtures

Use factory patterns for creating multiple test entities with automatic cleanup:

```python
import pytest

@pytest.fixture
def create_entity(home_assistant):
    """Factory fixture with automatic cleanup via given_an_entity."""
    def _create(entity_id, state):
        home_assistant.given_an_entity(entity_id, state)
        return entity_id

    return _create

def test_multiple_entities(create_entity):
    light1 = create_entity("light.test1", "on")
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

## Testing Area and Label Based Automations

Use the `EntityBuilder` returned by `given_an_entity()` to temporarily assign an area or labels to an entity for the duration of a test.
The harness automatically creates any missing area or label registry entries and restores the entity's original configuration after the test.

The builder works with both persistent entities and per-test entities created via `given_an_entity()`.
This means you can create a test-specific entity and immediately assign it an area or label — all within a single test:

```python
def test_per_test_entity_with_area_and_label(home_assistant):
    # Create a per-test light entity (registered in the entity registry)
    # and assign area and label via builder chain
    home_assistant.given_an_entity("light.test_light", "off") \
        .in_area("living_room") \
        .with_labels(["night_mode"])

    # Trigger automation targeting by label or area
    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.label_automation_trigger"})
    home_assistant.assert_entity_state("light.test_light", "on", timeout=10)
    # Entity and its config are both automatically cleaned up after the test
```

```python
def test_label_based_automation(home_assistant):
    # Assign the label — created in the label registry if it doesn't exist
    home_assistant.given_an_entity("light.living_room", "off") \
        .with_labels(["night_mode"])

    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.label_automation_trigger"})
    home_assistant.assert_entity_state("light.living_room", "on", timeout=10)
    # Labels are automatically restored after this test

def test_area_based_automation(home_assistant):
    # Assign the area — created in the area registry if it doesn't exist
    home_assistant.given_an_entity("light.living_room", "off") \
        .in_area("living_room")

    home_assistant.call_action("input_button", "press", {"entity_id": "input_button.area_automation_trigger"})
    home_assistant.assert_entity_state("light.living_room", "on", timeout=10)
    # Area assignment is automatically restored after this test
```

### Template Functions vs. Direct Targeting

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

The `EntityBuilder` creates the necessary registry entries for both cases, so your tests work regardless of which targeting style your automations use.
