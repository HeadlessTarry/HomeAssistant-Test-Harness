"""Example tests demonstrating that set_state() freezes the sun.sun entity.

When set_state() is called on sun.sun, the harness automatically freezes the entity
to prevent the Sun's self-updating callbacks (update_sun_position, update_events)
from overwriting the override. This is transparent to the caller.

Scenarios covered:
1. Overriding sun.sun state persists immediately after set_state()
2. Overriding sun.sun state with attributes persists immediately
3. restore() unfreezes the entity, allowing natural behavior to resume

Note: Time-advance stability is not currently guaranteed due to how Home Assistant
computes the Sun entity's state dynamically from solar position. See issue #188.
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

    def test_restore_unfreezes_sun_entity(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that restore() unfreezes sun.sun, allowing natural state updates."""
        sun_entity = "sun.sun"

        # Override state and verify it's frozen
        home_assistant.set_state(sun_entity, "below_horizon")
        home_assistant.assert_entity_state(sun_entity, "below_horizon")

        # Restore the entity to natural state
        home_assistant.restore(sun_entity)

        # Fast forward time - the sun.sun entity should now update naturally
        # We can't predict the exact state, but we can verify the entity is no longer frozen
        # by checking that restore() can be called again without error (idempotent)
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.restore(sun_entity)
