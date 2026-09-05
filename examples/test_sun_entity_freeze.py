"""Example tests demonstrating that set_state() freezes the sun.sun entity.

When set_state() is called on sun.sun, the harness automatically freezes the entity
to prevent the Sun's self-updating callbacks (update_sun_position, update_events)
from overwriting the override. This is transparent to the caller.

Scenarios covered:
1. Overriding sun.sun state persists immediately after set_state()
2. Overriding sun.sun state with attributes persists immediately
3. restore() unfreezes the entity, restoring original state
4. Overriding sun.sun state persists across time advances
"""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestSunEntityFreeze:
    """Tests for freezing the sun.sun entity."""

    def test_set_state_overrides_sun(self, home_assistant: HomeAssistant) -> None:
        """Test that set_state() on sun.sun persists immediately."""
        sun_entity = "sun.sun"

        # Override to a different state to prove we can control it
        home_assistant.set_state(sun_entity, "below_horizon")
        home_assistant.assert_entity_state(sun_entity, "below_horizon")
        home_assistant.set_state(sun_entity, "above_horizon")
        home_assistant.assert_entity_state(sun_entity, "above_horizon")

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

    def test_restore_unfreezes_sun_entity(self, home_assistant: HomeAssistant) -> None:
        """Test that restore() unfreezes sun.sun, restoring original state."""
        sun_entity = "sun.sun"

        # Read current natural state
        original_state = home_assistant.get_state(sun_entity)
        assert original_state is not None
        original_state_value = original_state["state"]

        # Override with a different state
        override_state = "above_horizon" if original_state_value == "below_horizon" else "below_horizon"
        home_assistant.set_state(sun_entity, override_state)
        home_assistant.assert_entity_state(sun_entity, override_state)

        # Restore and verify original state is back
        home_assistant.restore(sun_entity)
        home_assistant.assert_entity_state(sun_entity, original_state_value)

    def test_set_state_overrides_sun_persists_across_time_jumps(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that set_state() on sun.sun persists across time advances."""
        sun_entity = "sun.sun"

        home_assistant.set_state(sun_entity, "below_horizon")
        home_assistant.assert_entity_state(sun_entity, "below_horizon")

        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.assert_entity_state(sun_entity, "below_horizon")

        time_machine.fast_forward(timedelta(hours=11))
        home_assistant.assert_entity_state(sun_entity, "below_horizon")
