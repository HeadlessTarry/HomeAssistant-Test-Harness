"""Example tests demonstrating basic harness usage."""

import pytest

from ha_integration_test_harness import HomeAssistant


class TestAssertEntityState:

    an_entity = "sensor.test_entity"

    @pytest.fixture(autouse=True)
    def assign_test_entity(self, home_assistant: HomeAssistant) -> None:
        """Create the test entity."""
        home_assistant.given_an_entity(self.an_entity, state="on").with_attributes({"unit_of_measurement": "°C", "icon": "mdi:thermometer", "min": 10, "max": 30})

    def test_assert_entity_state_with_built_in_polling(self, home_assistant: HomeAssistant) -> None:
        """Test assert_entity_state with exact state value matching."""
        # Use-case 1: assert state exact match
        home_assistant.assert_entity_state(self.an_entity, "on")

    def test_assert_entity_state_with_exact_attribute_match(self, home_assistant: HomeAssistant) -> None:
        """Test assert_entity_state with exact attribute matching.

        Demonstrates use-cases 2 (state + attribute), 3 (attribute only) and 5 (lambda expressions):
        - #2: Assert state and a specific attribute match simultaneously.
        - #3: Assert only an attribute, without checking state.
        - #5: Assert attributes satisfy lambda expressions.
        """
        # Use-case 2: assert state AND attribute (singular) together
        home_assistant.assert_entity_state(self.an_entity, expected_state="on", expected_attributes={"icon": "mdi:thermometer"})

        # Use-case 3: assert attribute only (no state check)
        home_assistant.assert_entity_state(self.an_entity, expected_attributes={"icon": "mdi:thermometer"})

        # Use-case 5: assert multiple attributes at once
        home_assistant.assert_entity_state(
            self.an_entity,
            expected_attributes={"unit_of_measurement": "°C", "icon": "mdi:thermometer"},
        )

    def test_assert_entity_state_with_predicate_attribute(self, home_assistant: HomeAssistant) -> None:
        """Test assert_entity_state with lambda predicate for attribute values.

        Demonstrates use-case 4: assert an attribute using a lambda function
        instead of an exact value, enabling range or type checks.
        """
        # Use-case 4: use a lambda to assert the attribute value satisfies a condition
        home_assistant.assert_entity_state(
            self.an_entity,
            expected_attributes={
                "min": lambda v: float(v) >= 10,
                "max": lambda v: float(v) <= 30,
            },
        )

    def test_using_assert_to_check_entity_state(self, home_assistant: HomeAssistant) -> None:
        """Test that 'assert' can be used to check entity state"""
        # Verify state
        state = home_assistant.get_state(self.an_entity)
        assert state["state"] == "on"

    def test_polling_for_state_change(self, home_assistant: HomeAssistant) -> None:
        """Test polling until a state changes."""
        # Given a timer entity (see configuration.yaml in the test config directory)

        # Poll until timer goes idle (with timeout)
        home_assistant.assert_entity_state("timer.test_timer", "idle", timeout=10)

        # Cleanup
        home_assistant.remove_entity("timer.test_timer")
