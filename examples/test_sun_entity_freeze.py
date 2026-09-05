"""Example tests demonstrating that set_state() freezes the sun.sun entity.

When set_state() is called on sun.sun, the harness automatically freezes the entity
to prevent the Sun's self-updating callbacks (update_sun_position, update_events)
from overwriting the override. This is transparent to the caller.

Scenarios covered:
1. Overriding sun.sun state persists immediately after set_state()
2. Overriding sun.sun state with attributes persists immediately
"""

from ha_integration_test_harness import HomeAssistant


class TestSunEntityFreeze:
    """Tests for freezing the sun.sun entity."""

    def test_set_state_overrides_sun(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on sun.sun persists immediately."""
        sun_entity = "sun.sun"

        home_assistant.set_state(sun_entity, "below_horizon")
        home_assistant.assert_entity_state(sun_entity, "below_horizon")

    def test_set_state_overrides_sun_with_attributes(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on sun.sun with attributes persists."""
        sun_entity = "sun.sun"

        home_assistant.set_state(
            sun_entity,
            "above_horizon",
            {"friendly_name": "Test Sun"},
        )
        home_assistant.assert_entity_state(
            sun_entity,
            "above_horizon",
            {"friendly_name": "Test Sun"},
        )
