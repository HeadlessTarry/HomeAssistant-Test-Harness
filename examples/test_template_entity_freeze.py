"""Example tests demonstrating that set_state() freezes template entities.

When set_state() is called on a template entity, the harness automatically freezes
the entity to prevent template re-evaluation from overwriting the override. This is
transparent to the caller — no opt-in or extra parameter is needed.

Three scenarios are covered:

1. Overriding a template sensor:
   - set_state() overrides the template-computed state
   - Changing the underlying input entity does NOT overwrite the override

2. Overriding a template light:
   - Same behavior as template sensor, but with a light entity

3. Cleanup restores normal template behavior:
   - After the test, the template entity is unfrozen
   - Template re-evaluation works normally again
"""

import time

from ha_integration_test_harness import HomeAssistant


class TestTemplateSensorFreeze:
    """Tests for freezing template sensor entities."""

    def test_set_state_overrides_template_sensor_and_survives_re_evaluation(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on a template sensor persists even when the underlying entity changes.

        The template sensor 'sensor.template_test_sensor' derives its state from
        'input_boolean.state_template_sensor_source'. When set_state() overrides the
        sensor, changing the input boolean should NOT overwrite the override.
        """
        template_entity = "sensor.template_test_sensor"
        source_entity = "input_boolean.state_template_sensor_source"

        home_assistant.assert_entity_state(template_entity, "off")

        home_assistant.set_state(template_entity, "overridden_value")
        home_assistant.assert_entity_state(template_entity, "overridden_value")

        home_assistant.call_action("input_boolean", "turn_on", {"entity_id": source_entity})
        time.sleep(2)

        home_assistant.assert_entity_state(template_entity, "overridden_value")

    def test_template_sensor_responds_to_source_changes_when_not_frozen(self, home_assistant: HomeAssistant) -> None:
        """Test that the template sensor responds to source entity changes when not frozen.

        This test verifies that template sensors work normally (i.e., respond to source
        entity changes) when they haven't been frozen by set_state(). This demonstrates
        the baseline behavior that the freeze mechanism is designed to override.
        """
        template_entity = "sensor.template_test_sensor"
        source_entity = "input_boolean.state_template_sensor_source"

        # Ensure source is off and template reflects it
        home_assistant.call_action("input_boolean", "turn_off", {"entity_id": source_entity})
        home_assistant.assert_entity_state(template_entity, "off")

        # Change source and verify template follows
        home_assistant.call_action("input_boolean", "turn_on", {"entity_id": source_entity})
        home_assistant.assert_entity_state(template_entity, "on")


class TestTemplateLightFreeze:
    """Tests for freezing template light entities."""

    def test_set_state_overrides_template_light_and_survives_re_evaluation(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on a template light persists even when the underlying entity changes."""
        template_entity = "light.living_room_lamp"
        source_entity = "input_boolean.state_living_room_lamp"

        home_assistant.assert_entity_state(template_entity, "off")

        home_assistant.set_state(template_entity, "on", {"brightness": 128})
        home_assistant.assert_entity_state(template_entity, "on", {"brightness": 128})

        home_assistant.call_action("input_boolean", "turn_on", {"entity_id": source_entity})
        time.sleep(2)

        home_assistant.assert_entity_state(template_entity, "on", {"brightness": 128})

    def test_template_light_responds_to_source_changes_when_not_frozen(self, home_assistant: HomeAssistant) -> None:
        """Test that the template light responds to source entity changes when not frozen.

        This test verifies that template lights work normally (i.e., respond to source
        entity changes) when they haven't been frozen by set_state(). This demonstrates
        the baseline behavior that the freeze mechanism is designed to override.
        """
        template_entity = "light.living_room_lamp"
        source_entity = "input_boolean.state_living_room_lamp"

        # Ensure source is off and template reflects it
        home_assistant.call_action("input_boolean", "turn_off", {"entity_id": source_entity})
        home_assistant.assert_entity_state(template_entity, "off")

        # Change source and verify template follows
        home_assistant.call_action("input_boolean", "turn_on", {"entity_id": source_entity})
        home_assistant.assert_entity_state(template_entity, "on")


class TestNonTemplateEntitiesUnaffected:
    """Tests that non-template entities are unaffected by the freeze mechanism."""

    def test_set_state_on_regular_entity_works_normally(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on a non-template entity works as before."""
        entity_id = "sensor.regular_test_sensor"

        home_assistant.set_state(entity_id, "42", {"unit_of_measurement": "°C"})
        home_assistant.assert_entity_state(entity_id, "42", {"unit_of_measurement": "°C"})

        home_assistant.set_state(entity_id, "99", {"unit_of_measurement": "°F"})
        home_assistant.assert_entity_state(entity_id, "99", {"unit_of_measurement": "°F"})
