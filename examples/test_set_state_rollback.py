"""Example tests demonstrating automatic rollback of set_state() after each test.

This file demonstrates that state changes made via set_state() are automatically
rolled back after each test, preventing state leakage between tests.

Two scenarios are covered:

1. Modifying existing entities:
   - Entities defined in persistent_entities.yaml or created via given_an_entity()
   - Their state is snapshot before the first set_state() call
   - Restored to pre-test state after the test completes

2. Creating new entities via set_state():
   - Entities that don't exist before set_state() is called
   - Automatically removed after the test completes
"""

from ha_integration_test_harness import HomeAssistant


class TestSetStateRollbackForExistingEntities:
    """Tests for rollback of state changes to existing entities."""

    def test_set_state_modifies_persistent_entity(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() can modify a persistent entity's state."""
        # This entity is defined in persistent_entities.yaml with initial state "off"
        entity_id = "light.living_room_lamp"

        # Verify initial state
        home_assistant.assert_entity_state(entity_id, "off")

        # Modify the state
        home_assistant.set_state(entity_id, "on", {"brightness": 255})

        # Verify the state was modified
        home_assistant.assert_entity_state(entity_id, "on", {"brightness": 255})

    def test_persistent_entity_state_is_restored_after_modification(self, home_assistant: HomeAssistant) -> None:
        """Test that persistent entity state is restored after the previous test."""
        # This test runs after test_set_state_modifies_persistent_entity
        # The entity should be back to its original state
        entity_id = "light.living_room_lamp"

        # Verify the entity is back to its original state (not "on" with brightness 255)
        home_assistant.assert_entity_state(entity_id, "off")

    def test_set_state_multiple_times_only_snapshots_once(self, home_assistant: HomeAssistant) -> None:
        """Test that multiple set_state() calls only snapshot the original state once."""
        entity_id = "switch.garage_door"

        # Verify initial state
        home_assistant.assert_entity_state(entity_id, "off")

        # First set_state - should snapshot "off"
        home_assistant.set_state(entity_id, "on")
        home_assistant.assert_entity_state(entity_id, "on")

        # Second set_state - should NOT snapshot "on", original is still "off"
        home_assistant.set_state(entity_id, "on", {"power_consumption": 100})
        home_assistant.assert_entity_state(entity_id, "on", {"power_consumption": 100})

    def test_entity_restored_to_original_not_intermediate_state(self, home_assistant: HomeAssistant) -> None:
        """Test that entity is restored to original state, not intermediate state."""
        entity_id = "switch.garage_door"

        # After the previous test, entity should be back to "off" (not "on" with power_consumption)
        home_assistant.assert_entity_state(entity_id, "off")

    def test_set_state_with_attributes_restores_both(self, home_assistant: HomeAssistant) -> None:
        """Test that both state and attributes are restored."""
        entity_id = "input_boolean.guest_mode"

        # Verify initial state and attributes
        home_assistant.assert_entity_state(entity_id, "off", {"icon": "mdi:account-group"})

        # Modify both state and attributes
        home_assistant.set_state(entity_id, "on", {"icon": "mdi:account-check", "friendly_name": "Guest Mode Active"})

        # Verify modifications
        home_assistant.assert_entity_state(entity_id, "on", {"icon": "mdi:account-check"})

    def test_attributes_restored_after_modification(self, home_assistant: HomeAssistant) -> None:
        """Test that attributes are restored to original values."""
        entity_id = "input_boolean.guest_mode"

        # Should be back to original state and attributes
        home_assistant.assert_entity_state(entity_id, "off", {"icon": "mdi:account-group"})


class TestSetStateRollbackForNewEntities:
    """Tests for rollback of entities created via set_state()."""

    def test_set_state_creates_new_entity(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() can create a new entity that didn't exist before."""
        entity_id = "sensor.test_temperature"

        # Verify entity doesn't exist
        assert home_assistant.get_state(entity_id) is None

        # Create it via set_state
        home_assistant.set_state(entity_id, "22.5", {"unit_of_measurement": "°C"})

        # Verify it exists now
        home_assistant.assert_entity_state(entity_id, "22.5", {"unit_of_measurement": "°C"})

    def test_new_entity_removed_after_test(self, home_assistant: HomeAssistant) -> None:
        """Test that entities created via set_state() are removed after the test."""
        entity_id = "sensor.test_temperature"

        # Entity should be gone after the previous test
        assert home_assistant.get_state(entity_id) is None

    def test_multiple_new_entities_all_removed(self, home_assistant: HomeAssistant) -> None:
        """Test that multiple entities created via set_state() are all removed."""
        entities = [
            "sensor.new_entity_1",
            "binary_sensor.new_entity_2",
            "switch.new_entity_3",
        ]

        # Create multiple new entities
        for entity_id in entities:
            assert home_assistant.get_state(entity_id) is None
            home_assistant.set_state(entity_id, "on")
            home_assistant.assert_entity_state(entity_id, "on")

    def test_all_new_entities_removed(self, home_assistant: HomeAssistant) -> None:
        """Test that all entities created in the previous test are removed."""
        entities = [
            "sensor.new_entity_1",
            "binary_sensor.new_entity_2",
            "switch.new_entity_3",
        ]

        for entity_id in entities:
            assert home_assistant.get_state(entity_id) is None


class TestSetStateRollbackMixedScenarios:
    """Tests for mixed scenarios with both existing and new entities."""

    def test_mixed_existing_and_new_entities(self, home_assistant: HomeAssistant) -> None:
        """Test rollback with both existing and new entities in the same test."""
        existing_entity = "counter.doorbell_presses"
        new_entity = "sensor.mixed_test_sensor"

        # Verify initial states
        home_assistant.assert_entity_state(existing_entity, "0")
        assert home_assistant.get_state(new_entity) is None

        # Modify existing entity
        home_assistant.set_state(existing_entity, "5")

        # Create new entity
        home_assistant.set_state(new_entity, "100")

        # Verify both changes
        home_assistant.assert_entity_state(existing_entity, "5")
        home_assistant.assert_entity_state(new_entity, "100")

    def test_mixed_scenario_restored_correctly(self, home_assistant: HomeAssistant) -> None:
        """Test that mixed scenario is restored correctly."""
        existing_entity = "counter.doorbell_presses"
        new_entity = "sensor.mixed_test_sensor"

        # Existing entity should be restored
        home_assistant.assert_entity_state(existing_entity, "0")

        # New entity should be removed
        assert home_assistant.get_state(new_entity) is None
