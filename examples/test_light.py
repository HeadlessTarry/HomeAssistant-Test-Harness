"""Comprehensive tests for light entity support.

Tests cover the full HA light contract: brightness, color modes (color_temp_kelvin,
hs_color, rgb_color, xy_color), effects, flash, and transition.
"""

from ha_integration_test_harness import HomeAssistant


class TestLightBrightness:
    """Test brightness attribute handling."""

    def test_light_turn_on_with_brightness_via_action(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with brightness sets the brightness attribute."""
        light_entity = "light.test_brightness"
        home_assistant.given_an_entity(light_entity, state="off")
        home_assistant.assert_entity_state(light_entity, "off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "brightness": 100})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"brightness": 100})

    def test_light_turn_on_with_brightness_pct_via_action(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with brightness_pct converts to brightness."""
        light_entity = "light.test_brightness_pct"
        expected_brightness = round(25 / 100 * 255)  # 64
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "brightness_pct": 25})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"brightness": expected_brightness})

    def test_light_turn_on_with_brightness_pct_via_automation(self, home_assistant: HomeAssistant) -> None:
        """Test that automation with brightness_pct converts to brightness."""
        light_entity = "light.test_brightness_auto"
        expected_brightness = round(10 / 100 * 255)  # 26
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("input_button", "press", {"entity_id": "input_button.turn_on_brightness_light"})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"brightness": expected_brightness})


class TestLightColorModes:
    """Test color mode attribute handling."""

    def test_light_turn_on_with_color_temp_kelvin(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with color_temp_kelvin sets the attribute and color_mode."""
        light_entity = "light.test_color_temp"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "color_temp_kelvin": 4000})

        home_assistant.assert_entity_state(
            light_entity,
            expected_state="on",
            expected_attributes={"color_temp_kelvin": 4000, "color_mode": "color_temp"},
        )

    def test_light_turn_on_with_hs_color(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with hs_color sets the attribute and color_mode."""
        light_entity = "light.test_hs_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "hs_color": (180.0, 50.0)})

        home_assistant.assert_entity_state(
            light_entity,
            expected_state="on",
            expected_attributes={"hs_color": (180.0, 50.0), "color_mode": "hs"},
        )

    def test_light_turn_on_with_rgb_color(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with rgb_color sets the attribute and color_mode."""
        light_entity = "light.test_rgb_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "rgb_color": (255, 128, 0)})

        home_assistant.assert_entity_state(
            light_entity,
            expected_state="on",
            expected_attributes={"rgb_color": (255, 128, 0), "color_mode": "rgb"},
        )

    def test_light_turn_on_with_rgbw_color(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with rgbw_color sets the attribute and color_mode."""
        light_entity = "light.test_rgbw_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "rgbw_color": (255, 128, 0, 64)})

        home_assistant.assert_entity_state(
            light_entity,
            expected_state="on",
            expected_attributes={"rgbw_color": (255, 128, 0, 64), "color_mode": "rgbw"},
        )

    def test_light_turn_on_with_rgbww_color(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with rgbww_color sets the attribute and color_mode."""
        light_entity = "light.test_rgbww_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "rgbww_color": (255, 128, 0, 64, 32)})

        home_assistant.assert_entity_state(
            light_entity,
            expected_state="on",
            expected_attributes={"rgbww_color": (255, 128, 0, 64, 32), "color_mode": "rgbww"},
        )

    def test_light_turn_on_with_xy_color(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with xy_color sets the attribute."""
        light_entity = "light.test_xy_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "xy_color": (0.3, 0.5)})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"xy_color": (0.3, 0.5)})

    def test_light_cross_format_derivation(self, home_assistant: HomeAssistant) -> None:
        """Test that setting hs_color derives rgb_color and xy_color via HA state_attributes."""
        light_entity = "light.test_cross_format"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "hs_color": (0.0, 100.0)})

        state = home_assistant.get_state(light_entity)
        assert state is not None
        assert state["state"] == "on"
        assert "rgb_color" in state["attributes"]
        assert "xy_color" in state["attributes"]
        rgb = state["attributes"]["rgb_color"]
        assert rgb[0] > 250 and rgb[1] < 5 and rgb[2] < 5


class TestLightFeatures:
    """Test effect, flash, and transition features."""

    def test_light_turn_on_with_effect(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with effect sets the attribute."""
        light_entity = "light.test_effect"
        home_assistant.given_an_entity(light_entity, state="off", attributes={"effect_list": ["colorloop", "random"]})

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "effect": "colorloop"})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"effect": "colorloop"})

    def test_light_turn_on_with_transition(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_on with transition does not cause errors."""
        light_entity = "light.test_transition"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.call_action("light", "turn_on", {"entity_id": light_entity, "transition": 5})

        home_assistant.assert_entity_state(light_entity, expected_state="on")

    def test_light_turn_off_with_transition(self, home_assistant: HomeAssistant) -> None:
        """Test that light.turn_off with transition does not cause errors."""
        light_entity = "light.test_transition_off"
        home_assistant.given_an_entity(light_entity, state="on")

        home_assistant.call_action("light", "turn_off", {"entity_id": light_entity, "transition": 3})

        home_assistant.assert_entity_state(light_entity, expected_state="off")


class TestLightSetVirtualState:
    """Test set_virtual_state with light attributes."""

    def test_set_virtual_state_with_brightness(self, home_assistant: HomeAssistant) -> None:
        """Test that set_virtual_state accepts brightness."""
        light_entity = "light.test_set_state_brightness"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.set_state(light_entity, "on", {"brightness": 150})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"brightness": 150})

    def test_set_virtual_state_with_color(self, home_assistant: HomeAssistant) -> None:
        """Test that set_virtual_state accepts color attributes."""
        light_entity = "light.test_set_state_color"
        home_assistant.given_an_entity(light_entity, state="off")

        home_assistant.set_state(light_entity, "on", {"hs_color": (240.0, 75.0)})

        home_assistant.assert_entity_state(light_entity, expected_state="on", expected_attributes={"hs_color": (240.0, 75.0)})
