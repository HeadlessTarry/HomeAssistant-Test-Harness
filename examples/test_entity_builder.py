"""Tests for the fluent EntityBuilder API."""

from ha_integration_test_harness import HomeAssistant


class TestEntityBuilderBasic:
    """Basic tests for EntityBuilder fluent API."""

    def test_given_an_entity_returns_builder(self, home_assistant: HomeAssistant) -> None:
        """Test that given_an_entity() returns an EntityBuilder instance."""
        builder = home_assistant.given_an_entity("sensor.test_builder", "0")
        assert builder is not None
        assert hasattr(builder, "with_device_class")
        assert hasattr(builder, "in_area")
        assert hasattr(builder, "with_labels")
        assert hasattr(builder, "with_attributes")

    def test_builder_with_device_class(self, home_assistant: HomeAssistant) -> None:
        """Test that with_device_class() sets the device_class attribute."""
        home_assistant.given_an_entity("binary_sensor.test_motion", "off").with_device_class("motion")
        state = home_assistant.get_state("binary_sensor.test_motion")
        assert state is not None
        assert state.get("attributes", {}).get("device_class") == "motion"

    def test_builder_in_area(self, home_assistant: HomeAssistant) -> None:
        """Test that in_area() assigns the entity to an area."""
        home_assistant.given_an_entity("light.test_area_light", "off").in_area("test_room")
        config = home_assistant._get_entity_config("light.test_area_light")
        assert config["area_id"] == "test_room"

    def test_builder_with_labels(self, home_assistant: HomeAssistant) -> None:
        """Test that with_labels() assigns labels to the entity."""
        home_assistant.given_an_entity("switch.test_labeled_switch", "off").with_labels(["test_label"])
        config = home_assistant._get_entity_config("switch.test_labeled_switch")
        assert "test_label" in config["labels"]

    def test_builder_with_attributes(self, home_assistant: HomeAssistant) -> None:
        """Test that with_attributes() sets custom attributes."""
        home_assistant.given_an_entity("sensor.test_custom_attrs", "21.5").with_attributes({"unit_of_measurement": "°C", "icon": "mdi:thermometer"})
        state = home_assistant.get_state("sensor.test_custom_attrs")
        assert state is not None
        attrs = state.get("attributes", {})
        assert attrs.get("unit_of_measurement") == "°C"
        assert attrs.get("icon") == "mdi:thermometer"


class TestEntityBuilderChaining:
    """Tests for EntityBuilder method chaining."""

    def test_chain_device_class_and_area(self, home_assistant: HomeAssistant) -> None:
        """Test chaining with_device_class() and in_area()."""
        home_assistant.given_an_entity("binary_sensor.test_chain_basic", "off").with_device_class("motion").in_area("study")

        state = home_assistant.get_state("binary_sensor.test_chain_basic")
        assert state is not None
        assert state.get("attributes", {}).get("device_class") == "motion"

        config = home_assistant._get_entity_config("binary_sensor.test_chain_basic")
        assert config["area_id"] == "study"

    def test_chain_area_with_labels(self, home_assistant: HomeAssistant) -> None:
        """Test chaining in_area() and with_labels()."""
        home_assistant.given_an_entity("light.test_chain_labels", "off").in_area("study").with_labels(["presence"])

        state = home_assistant.get_state("light.test_chain_labels")
        assert state is not None

        config = home_assistant._get_entity_config("light.test_chain_labels")
        assert config["area_id"] == "study"
        assert "presence" in config["labels"]

    def test_chain_multiple_attributes(self, home_assistant: HomeAssistant) -> None:
        """Test that successive with_attributes() calls merge attributes."""
        home_assistant.given_an_entity("sensor.test_chain_merge", "21.5").with_attributes({"unit_of_measurement": "°C"}).with_attributes({"icon": "mdi:thermometer", "min": 10})

        state = home_assistant.get_state("sensor.test_chain_merge")
        assert state is not None
        attrs = state.get("attributes", {})
        assert attrs.get("unit_of_measurement") == "°C"
        assert attrs.get("icon") == "mdi:thermometer"
        assert attrs.get("min") == 10

    def test_full_chain(self, home_assistant: HomeAssistant) -> None:
        """Test a full chain with all builder methods."""
        home_assistant.given_an_entity("binary_sensor.test_full_chain", "off").with_device_class("occupancy").in_area("study").with_labels(["presence", "security"]).with_attributes(
            {"custom_attr": "value"}
        )

        state = home_assistant.get_state("binary_sensor.test_full_chain")
        assert state is not None
        assert state.get("state") == "off"
        assert state.get("attributes", {}).get("device_class") == "occupancy"
        assert state.get("attributes", {}).get("custom_attr") == "value"

        config = home_assistant._get_entity_config("binary_sensor.test_full_chain")
        assert config["area_id"] == "study"
        assert "presence" in config["labels"]
        assert "security" in config["labels"]


class TestEntityBuilderReEntry:
    """Tests for EntityBuilder re-entry behavior."""

    def test_reentry_returns_new_builder(self, home_assistant: HomeAssistant) -> None:
        """Test that calling given_an_entity() twice returns a new builder."""
        builder1 = home_assistant.given_an_entity("sensor.test_reentry", "0")
        builder2 = home_assistant.given_an_entity("sensor.test_reentry", "1")

        assert builder1 is not builder2
        state = home_assistant.get_state("sensor.test_reentry")
        assert state is not None
        assert state.get("state") == "1"

    def test_reentry_updates_state(self, home_assistant: HomeAssistant) -> None:
        """Test that re-entry updates the entity state."""
        home_assistant.given_an_entity("sensor.test_reentry_state", "initial")
        home_assistant.given_an_entity("sensor.test_reentry_state", "updated")

        state = home_assistant.get_state("sensor.test_reentry_state")
        assert state is not None
        assert state.get("state") == "updated"


class TestEntityBuilderRollback:
    """Tests for EntityBuilder rollback tracking."""

    def test_builder_triggers_rollback_tracking(self, home_assistant: HomeAssistant) -> None:
        """Test that builder methods trigger rollback tracking."""
        home_assistant.given_an_entity("light.test_rollback", "off").in_area("test_area")

        assert "light.test_rollback" in home_assistant._entity_original_config

    def test_labels_trigger_rollback_tracking(self, home_assistant: HomeAssistant) -> None:
        """Test that with_labels() triggers rollback tracking."""
        home_assistant.given_an_entity("switch.test_rollback_labels", "off").with_labels(["test_label"])

        assert "switch.test_rollback_labels" in home_assistant._entity_original_config
