"""Example tests demonstrating automatic entity cleanup and persistent entities.

This file demonstrates two entity management patterns:

1. Per-test entities via given_an_entity():
   - Created during a test via home_assistant.given_an_entity()
   - Automatically cleaned up after each test
   - Useful for test-specific temporary entities
   - Helps avoid test pollution and cross-test coupling

2. Persistent session entities:
   - Defined in a YAML file (persistent_entities.yaml) referenced via pyproject.toml
   - Registered with Home Assistant during container startup
   - Available throughout the entire test session
   - Never automatically removed
   - Useful for simulating integration-created entities that tests depend on

To use persistent entities:
1. Create a YAML file with entity definitions (see persistent_entities.yaml)
2. Add to your pyproject.toml:
   [tool.pytest.ini_options]
   ha_persistent_entities_path = "path/to/entities.yaml"
"""

import pytest

from ha_integration_test_harness import HomeAssistant


class TestEntitiesManagedByTests:

    supported_domains = ["sensor", "binary_sensor", "switch", "light", "media_player", "select"]
    test_entities = [f"{domain}.per_test_entity" for domain in supported_domains]

    @pytest.fixture(autouse=True)
    def create_test_entities(self, home_assistant: HomeAssistant) -> None:
        """Create the test entities."""
        for entity in self.test_entities:
            home_assistant.given_an_entity(entity, state="off", attributes={"attr_key": "attr_val"})
        # No manual cleanup needed - the fixture will handle it automatically!

    def test_read_state_of_created_entities(self, home_assistant: HomeAssistant) -> None:
        """Test that state of entities created via given_an_entity() can be read back."""
        # All created entities are available to read back
        for entity in self.test_entities:
            home_assistant.assert_entity_state(entity, expected_state="off", expected_attributes={"attr_key": "attr_val"})

    def test_entity_created_multiple_times_overwrites_state(self, home_assistant: HomeAssistant) -> None:
        """Test that updating an entity via given_an_entity() doesn't create duplicates."""
        sample_entity = self.test_entities[0]
        # Re-create the same entity but with updated state and attributes
        home_assistant.given_an_entity(sample_entity, "on", attributes={"updated": True})

        home_assistant.assert_entity_state(sample_entity, expected_state="on", expected_attributes={"updated": True})

    def test_entity_creation_within_test_function(self, home_assistant: HomeAssistant) -> None:
        """Test that entities can be created via given_an_entity() during test functions."""
        entity_id = "switch.entity_created_within_test_function"
        # Test entities created in this way would still be automatically cleaned up
        home_assistant.given_an_entity(entity_id, "on")
        home_assistant.assert_entity_state(entity_id, expected_state="on")

    def test_entities_can_be_removed(self, home_assistant: HomeAssistant) -> None:
        """Test that entities can be removed via remove_entity() during test functions."""
        sample_entity = self.test_entities[0]
        # Verify entity state can be read
        home_assistant.assert_entity_state(sample_entity, expected_state="off")

        home_assistant.remove_entity(sample_entity)

        # Confirm the entity no longer exists in the state machine
        assert home_assistant.get_state(sample_entity) is None

    def test_entity_created_modified_then_removed(self, home_assistant: HomeAssistant) -> None:
        """Test that teardown succeeds when an entity is created, modified, then removed.

        This reproduces issue #165: when a test creates an entity via given_an_entity(),
        modifies it via set_state(), then removes it via remove_entity(), teardown should
        not attempt to restore state for the removed entity.
        """
        entity_id = "switch.test_create_modify_remove"

        # Create entity
        home_assistant.given_an_entity(entity_id, state="off", attributes={"foo": "bar"})
        home_assistant.assert_entity_state(entity_id, expected_state="off", expected_attributes={"foo": "bar"})

        # Modify entity state
        home_assistant.set_state(entity_id, state="on", attributes={"foo": "baz"})
        home_assistant.assert_entity_state(entity_id, expected_state="on", expected_attributes={"foo": "baz"})

        # Remove entity
        home_assistant.remove_entity(entity_id)

        # Confirm the entity no longer exists
        assert home_assistant.get_state(entity_id) is None

        # Test passes, but teardown should not fail with "Entity not found" errors


class TestEntitiesWithAreasAndLabels:

    light_entity = "light.test_light_entity"

    @pytest.fixture(autouse=True)
    def create_test_entities(self, home_assistant: HomeAssistant) -> None:
        """Create the test entity."""
        home_assistant.given_an_entity(self.light_entity, state="off")
        # Assign an area and a label to the newly created entity
        home_assistant.given_entity_has(self.light_entity, area="test_room", labels=["test_label_target"])

    def test_given_an_entity_then_assign_area_and_label(self, home_assistant: HomeAssistant) -> None:
        """Test that an entity created via given_an_entity() supports area and label assignment.

        Because given_an_entity() registers entities in the HA entity registry (with a
        unique_id), they can be targeted by given_entity_has() in the same test — a
        combination that was not possible with REST-based entity creation.
        """
        # Entity state should still be readable after registry updates
        home_assistant.assert_entity_state(self.light_entity, "off")

    def test_label_based_automation(self, home_assistant: HomeAssistant) -> None:
        """Test that a label-based automation turns on a light assigned the target label.

        An automation in configuration.yaml fires when input_button.label_automation_trigger
        is pressed and turns on all entities carrying the 'test_label_target' label.

        This test assigns that label to a light entity, presses the button,
        and verifies the light turns on. The label is automatically restored to its
        original value (no labels) after the test function completes.
        """
        # Ensure the light starts off before triggering the automation
        home_assistant.assert_entity_state(self.light_entity, "off")

        # Press the button — triggers the automation that uses label-based targeting
        home_assistant.call_action("input_button", "press", {"entity_id": "input_button.label_automation_trigger"})

        # The automation should turn on the light that carries the label
        home_assistant.assert_entity_state(self.light_entity, "on")

    def test_area_based_automation(self, home_assistant: HomeAssistant) -> None:
        """Test that an area-based automation turns on a light assigned to the target area.

        An automation in configuration.yaml fires when input_button.area_automation_trigger
        is pressed and turns on all lights in the 'test_room' area.

        This test assigns the 'test_room' area to a light entity, presses the
        button, and verifies the light turns on. The area assignment is automatically
        restored to its original value (no area) after the test function completes.
        """
        # Ensure the light starts off before triggering the automation
        home_assistant.assert_entity_state(self.light_entity, "off")

        # Press the button — triggers the automation that uses area-based targeting
        home_assistant.call_action("input_button", "press", {"entity_id": "input_button.area_automation_trigger"})

        # The automation should turn on the light that belongs to the area
        home_assistant.assert_entity_state(self.light_entity, "on")


class TestPersistentEntities:

    def test_persistent_entities_available_with_expected_initial_state(self, home_assistant: HomeAssistant) -> None:
        """Test that persistent entities exist and have expected initial state.

        This test demonstrates that persistent entities (defined via the
        ha_persistent_entities_path configuration) are registered during
        container startup, available to all tests, and initialized to expected
        values from persistent_entities.yaml.
        """
        home_assistant.assert_entity_state("counter.doorbell_presses", "0")
        home_assistant.assert_entity_state("light.living_room_lamp", "off")
        home_assistant.assert_entity_state("switch.garage_door", "off")
        home_assistant.assert_entity_state("input_boolean.guest_mode", expected_state="off", expected_attributes={"icon": "mdi:account-group"})
        home_assistant.assert_entity_state("input_number.target_temperature", expected_state="20.0", expected_attributes={"min": 10, "max": 30})
        home_assistant.assert_entity_state("input_select.house_mode", expected_state="Home", expected_attributes={"options": ["Home", "Away", "Night"]})


class TestCallHomeAssitantActions:

    # Not all domains offer `turn_on`/`turn_off` action calls
    supported_domains = ["switch", "light", "media_player"]

    def test_call_domain_specific_turn_on_and_off_actions(self, home_assistant: HomeAssistant) -> None:
        """Test calling a 'turn_on' action for a supported entity domain."""
        # media_player transitions to "idle" on turn_on (not "on") since it has no media to play
        expected_on_state = {"switch": "on", "light": "on", "media_player": "idle"}
        for domain in self.supported_domains:
            entity_id = f"{domain}.test_entity"
            home_assistant.given_an_entity(entity_id, state="off")

            # Verify initial state is off
            home_assistant.assert_entity_state(entity_id, "off")

            # Call "Turn On" action
            home_assistant.call_action(domain, "turn_on", {"entity_id": entity_id})

            # Verify the entity was turned on (media_player goes to "idle" instead of "on")
            home_assistant.assert_entity_state(entity_id, expected_on_state[domain])

            # Call "Turn Off" action
            home_assistant.call_action(domain, "turn_off", {"entity_id": entity_id})

            # Verify the entity was turned off
            home_assistant.assert_entity_state(entity_id, "off")


class TestMediaPlayerEntity:

    def test_create_media_player_entity(self, home_assistant: HomeAssistant) -> None:
        """Test that a media_player entity can be created via given_an_entity()."""
        home_assistant.given_an_entity("media_player.test_tv", "off")
        home_assistant.assert_entity_state("media_player.test_tv", "off")

    def test_media_player_turn_on_off(self, home_assistant: HomeAssistant) -> None:
        """Test that turn_on/turn_off actions transition media_player state correctly."""
        home_assistant.given_an_entity("media_player.test_tv", "off")

        home_assistant.call_action("media_player", "turn_on", {"entity_id": "media_player.test_tv"})
        home_assistant.assert_entity_state("media_player.test_tv", "idle")

        home_assistant.call_action("media_player", "turn_off", {"entity_id": "media_player.test_tv"})
        home_assistant.assert_entity_state("media_player.test_tv", "off")

    def test_media_player_set_arbitrary_state(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() works for arbitrary media_player state strings."""
        home_assistant.given_an_entity("media_player.test_tv", "off")

        home_assistant.set_state("media_player.test_tv", "playing", {"media_title": "Test Song"})
        home_assistant.assert_entity_state("media_player.test_tv", "playing", expected_attributes={"media_title": "Test Song"})

        home_assistant.set_state("media_player.test_tv", "paused")
        home_assistant.assert_entity_state("media_player.test_tv", "paused")


class TestSelectEntity:

    def test_create_select_entity_with_options(self, home_assistant: HomeAssistant) -> None:
        """Test that a select entity can be created with options via given_an_entity()."""
        home_assistant.given_an_entity(
            "select.house_mode",
            "Home",
            attributes={"options": ["Home", "Away", "Night"]},
        )
        home_assistant.assert_entity_state("select.house_mode", "Home", expected_attributes={"options": ["Home", "Away", "Night"]})

    def test_select_option_via_action(self, home_assistant: HomeAssistant) -> None:
        """Test that select_option action changes the selected option."""
        home_assistant.given_an_entity(
            "select.house_mode",
            "Home",
            attributes={"options": ["Home", "Away", "Night"]},
        )

        home_assistant.call_action("select", "select_option", {"entity_id": "select.house_mode", "option": "Away"})
        home_assistant.assert_entity_state("select.house_mode", "Away")

    def test_select_options_accessible(self, home_assistant: HomeAssistant) -> None:
        """Test that the options list is accessible in entity state attributes."""
        home_assistant.given_an_entity(
            "select.house_mode",
            "Home",
            attributes={"options": ["Home", "Away", "Night"]},
        )
        state = home_assistant.get_state("select.house_mode")
        assert state is not None
        assert state["attributes"]["options"] == ["Home", "Away", "Night"]
