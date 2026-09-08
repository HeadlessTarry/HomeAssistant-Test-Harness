"""Example tests demonstrating time_machine.override_sun() for controlling sun conditions.

The sun conditions (sun.is_set, sun.is_up, etc.) compute astronomically from the astral
library and HA config lat/lon/elevation. They do NOT read the sun.sun entity state.
override_sun() patches the underlying helpers to force sun conditions to return the
desired values, independent of the actual fake time.

Scenarios covered:
1. override_sun("below_horizon") makes condition: sun.is_set pass
2. override_sun("above_horizon") makes condition: sun.is_set fail
3. override_sun(elevation=...) works for elevation-based control
4. set_state("sun.sun", ...) auto-overrides conditions
5. Teardown restores time-aligned sun state
6. Last-call-wins for transition simulation
7. Invalid inputs raise errors
"""

from datetime import timedelta

import pytest

from ha_integration_test_harness import HomeAssistant, TimeMachine

SUN_TEST_LIGHT = "light.sun_test_light"


class TestSunOverride:
    """Tests for time_machine.override_sun()."""

    def test_override_sun_below_horizon_triggers_is_set_condition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun('below_horizon') makes condition: sun.is_set pass."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=18, minute=44)

        time_machine.override_sun("below_horizon")

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "on")

    def test_override_sun_above_horizon_blocks_is_set_condition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun('above_horizon') makes condition: sun.is_set fail."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=18, minute=44)

        time_machine.override_sun("above_horizon")

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "off")

    def test_override_sun_above_horizon_triggers_is_up_condition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun('above_horizon') makes condition: sun.is_up pass."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=6, minute=59)

        time_machine.override_sun("above_horizon")

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "on")

    def test_override_sun_below_horizon_blocks_is_up_condition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun('below_horizon') makes condition: sun.is_up fail."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=6, minute=59)

        time_machine.override_sun("below_horizon")

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "off")

    def test_override_sun_with_elevation(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun(elevation=...) works for elevation-based control."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=18, minute=44)

        time_machine.override_sun(elevation=-5.0)

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "on")

    def test_override_sun_sets_entity_state_and_attributes(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun sets sun.sun entity state and plausible attributes."""
        time_machine.override_sun("below_horizon")

        sun_state = home_assistant.get_state("sun.sun")
        assert sun_state["state"] == "below_horizon"
        assert "elevation" in sun_state["attributes"]
        assert sun_state["attributes"]["elevation"] < 0

    def test_override_sun_with_elevation_sets_entity_state(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun(elevation=...) derives entity state from elevation."""
        time_machine.override_sun(elevation=-5.0)

        sun_state = home_assistant.get_state("sun.sun")
        assert sun_state["state"] == "below_horizon"
        assert sun_state["attributes"]["elevation"] == -5.0

    def test_set_state_sun_sun_auto_overrides_conditions(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that set_state('sun.sun', ...) auto-overrides conditions."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=18, minute=44)

        home_assistant.set_state("sun.sun", "below_horizon")

        time_machine.fast_forward(timedelta(minutes=1, seconds=15))

        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "on")

    def test_override_sun_last_call_wins(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that multiple override_sun calls use the last value (transition sim)."""
        home_assistant.given_an_entity(SUN_TEST_LIGHT, "off")
        time_machine.jump_to_next(hour=18, minute=43)

        time_machine.override_sun("above_horizon")
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "off")

        time_machine.override_sun("below_horizon")
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.assert_entity_state(SUN_TEST_LIGHT, "on")

    def test_override_sun_teardown_restores_time_aligned(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that teardown restores sun to time-aligned calculation."""
        time_machine.jump_to_next(hour=3, minute=0)

        time_machine.override_sun("above_horizon")
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

        time_machine.fast_forward(timedelta(hours=1))

        sun_state = home_assistant.get_state("sun.sun")
        assert sun_state["state"] == "above_horizon"

    def test_override_sun_invalid_state_raises(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun with invalid state string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sun state"):
            time_machine.override_sun("invalid_state")

    def test_override_sun_invalid_elevation_raises(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun with invalid elevation raises ValueError."""
        with pytest.raises(ValueError, match="elevation"):
            time_machine.override_sun(elevation=100.0)

        with pytest.raises(ValueError, match="elevation"):
            time_machine.override_sun(elevation=-100.0)

    def test_override_sun_no_args_raises(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        """Test that override_sun with no arguments raises ValueError."""
        with pytest.raises(ValueError, match="state.*elevation"):
            time_machine.override_sun()
