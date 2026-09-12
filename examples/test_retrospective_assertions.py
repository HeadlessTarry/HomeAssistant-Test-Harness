"""Example tests demonstrating retrospective time-window assertions."""

from datetime import time, timedelta

import pytest

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestRetrospectiveAssertions:
    """Demonstrate assert_entity_was_in_state usage."""

    an_entity = "sensor.test_entity"

    @pytest.fixture(autouse=True)
    def assign_test_entity(self, home_assistant: HomeAssistant) -> None:
        """Create the virtual entity."""
        home_assistant.given_an_entity(self.an_entity, state="off").with_attributes({"brightness": 0})

    def test_transition_mode_basic(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test transition mode: entity entered expected state during window."""
        # Move time past the entity creation time
        time_machine.fast_forward(timedelta(seconds=5))
        start_of_window = time_machine.get_current_local_time()

        # Change state within the window
        home_assistant.set_state(self.an_entity, "on", {"brightness": 255})

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Verify the entity was "on" at some point during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(start_of_window.time(), end_of_window.time()),
        )

        # Verify we got matching entries
        assert len(entries) > 0
        assert entries[0]["state"] == "on"

    def test_full_duration_entity_created_during_window(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test full-duration mode when entity is created during the window.

        Regression test for issue #204: assert_entity_was_in_state fails when entity
        is created during window in expected state.

        When an entity is created during the assertion window in the expected state
        and never changes state, the assertion should pass with require_full_duration=True.
        """
        start_of_window = time_machine.get_current_local_time()

        # Move past start of window and create entity
        one_minute = timedelta(minutes=1)
        time_machine.fast_forward(one_minute)
        entity = "light.test_entity_created_mid_window"
        home_assistant.given_an_entity(entity, state="off")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Assert entity was "off" throughout the entire window
        # This should pass because the entity was created in "off" state and never changed
        entries = home_assistant.assert_entity_was_in_state(
            entity,
            "off",
            between=(start_of_window.time(), end_of_window.time()),
            require_full_duration=True,
        )

        assert len(entries) > 0
        assert entries[0]["state"] == "off"

    def test_full_duration_entity_created_during_window_wrong_state(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test full-duration mode when entity is created during the window in wrong state.

        When an entity is created during the assertion window in a different state than
        expected, the assertion should fail with require_full_duration=True.
        """
        start_of_window = time_machine.get_current_local_time()

        # Move past start of window and create entity - with a state not matching expected
        time_machine.fast_forward(timedelta(minutes=1))
        entity = "light.test_entity_created_mid_window_wrong_state"
        home_assistant.given_an_entity(entity, state="on")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Assert entity was "off" throughout the entire window
        # This should fail because the entity was created in "on" state
        with pytest.raises(AssertionError, match="was not in state 'off' throughout the entire window"):
            home_assistant.assert_entity_was_in_state(
                entity,
                "off",
                between=(start_of_window.time(), end_of_window.time()),
                require_full_duration=True,
            )

    def test_full_duration_entity_existed_before_window(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test full-duration mode when entity existed before window and changed during it.

        When an entity existed before the assertion window and changed to the expected state
        during the window, the assertion should fail with require_full_duration=True.
        """
        # Entity created in "off" state via pytest fixture

        # Establish the start of window after entity was created
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Advance time, and change entity state (mid-window)
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "on")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Assert entity was "off" throughout the entire window
        # This should fail because the entity changed to "on" mid-window
        with pytest.raises(AssertionError, match="was not in state 'off' throughout the entire window"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "off",
                between=(start_of_window.time(), end_of_window.time()),
                require_full_duration=True,
            )

    def test_full_duration_mode(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test full-duration mode: entity remained in expected state throughout window."""
        # Entity created in "off" state via pytest fixture

        # Establish the start of window after entity creation
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Set the same state again
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "off")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Assert entity was "off" throughout the entire window
        # This should pass because the entity was created in "off" state and never changed
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "off",
            between=(start_of_window.time(), end_of_window.time()),
            require_full_duration=True,
        )

        assert len(entries) > 0
        assert entries[0]["state"] == "off"

    def test_attribute_matching(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with attribute matching."""
        # Establish the start of window
        start_of_window = time_machine.get_current_local_time()

        # Advance time and adjust attribute
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "on", attributes={"brightness": 128})

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(start_of_window.time(), end_of_window.time()),
            expected_attributes={"brightness": 128},
        )

        assert len(entries) > 0
        assert entries[0]["attributes"]["brightness"] == 128

    def test_predicate_state(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with predicate function for state."""
        # Establish start time
        start_of_window = time_machine.get_current_local_time()

        # Change state within the window
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "42")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Verify the entity was "on" at some point during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            lambda s: s.isdigit() and int(s) > 40,
            between=(start_of_window.time(), end_of_window.time()),
        )

        # Verify we got matching entries
        assert len(entries) > 0
        assert int(entries[0]["state"]) > 40

    def test_predicate_attribute(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with predicate function for attributes."""
        # Establish start time
        start_of_window = time_machine.get_current_local_time()

        # Change state within the window
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "on", attributes={"brightness": 160})

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Verify the entity was "on" at some point during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity, "on", between=(start_of_window.time(), end_of_window.time()), expected_attributes={"brightness": lambda v: v is not None and v >= 150}
        )

        # Verify we got matching entries
        assert len(entries) > 0
        assert entries[0]["attributes"]["brightness"] >= 150

    def test_attribute_only_check(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with attribute-only check (no state check)."""
        # Establish start time
        start_of_window = time_machine.get_current_local_time()

        # Change state within the window
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "on", {"brightness": 100})

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # Verify the entity was "on" at some point during the window
        entries = home_assistant.assert_entity_was_in_state(self.an_entity, None, between=(start_of_window.time(), end_of_window.time()), expected_attributes={"brightness": 100})

        assert len(entries) > 0

    def test_failure_no_history(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that assertion fails when no history exists in the window."""
        # Create a fresh entity that has no history
        fresh_entity = "sensor.fresh_entity"
        home_assistant.given_an_entity(fresh_entity, state="initial")

        # Establish start time
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        # This should fail because no state changes occurred in that window
        with pytest.raises(AssertionError, match="No state changes recorded|was not in state"):
            home_assistant.assert_entity_was_in_state(
                fresh_entity,
                "on",
                between=(start_of_window.time(), end_of_window.time()),
            )

    def test_failure_state_not_matched(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that assertion fails when state doesn't match."""
        # Establish start time
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        with pytest.raises(AssertionError, match="was not in state"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "never_this_state",
                between=(start_of_window.time(), end_of_window.time()),
            )

    def test_failure_full_duration_not_met(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that full-duration assertion fails when state changes during window."""
        # Entity created in "off" state via pytest fixture

        # Establish the start of window after entity creation
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Set the expected state, but after the window starts
        time_machine.fast_forward(timedelta(minutes=1))
        home_assistant.set_state(self.an_entity, "on")

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        with pytest.raises(AssertionError, match="was not in state"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
                between=(start_of_window.time(), end_of_window.time()),
                require_full_duration=True,
            )

    def test_zero_width_window_raises(self, home_assistant: HomeAssistant) -> None:
        """Test that zero-width window raises ValueError."""
        with pytest.raises(ValueError, match="Zero-width time window"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
                between=(time(12, 0), time(12, 0)),
            )

    def test_missing_between_raises(self, home_assistant: HomeAssistant) -> None:
        """Test that missing 'between' parameter raises ValueError."""
        with pytest.raises(ValueError, match="'between' parameter is required"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
            )

    def test_no_expected_state_or_attributes_raises(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that missing both expected_state and expected_attributes raises ValueError."""
        start_of_window = time_machine.get_current_local_time()

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        with pytest.raises(ValueError, match="At least one of expected_state or expected_attributes"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                None,
                between=(start_of_window.time(), end_of_window.time()),
            )

    def test_future_window_fails(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that a window entirely in the future fails with no history."""
        current_local_time = time_machine.get_current_local_time()

        in_the_future = (current_local_time + timedelta(minutes=30)).time()
        further_in_future = (current_local_time + timedelta(minutes=60)).time()

        with pytest.raises(AssertionError, match="does not match expectations|No state changes recorded|not found in history"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
                between=(in_the_future, further_in_future),
            )

    def test_attribute_matching_full_duration(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test attribute matching in full-duration mode."""
        home_assistant.set_state(self.an_entity, "on", {"brightness": 200, "color_temp": 3000})

        # Establish the start of window
        time_machine.fast_forward(timedelta(minutes=1))
        start_of_window = time_machine.get_current_local_time()

        # Advance time to end of window
        time_machine.fast_forward(timedelta(minutes=5))
        end_of_window = time_machine.get_current_local_time()

        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(start_of_window.time(), end_of_window.time()),
            expected_attributes={"brightness": 200},
            require_full_duration=True,
        )

        assert len(entries) > 0
        assert entries[0]["attributes"]["brightness"] == 200

    def test_between_times_are_local_not_utc(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that between times are interpreted as local times, not UTC.

        Regression test for issue #199: assert_entity_was_in_state treats between
        times as UTC instead of local time, causing seasonal breakage during DST.

        This test sets the fake clock to 18:00 BST (17:00 UTC) on September 12, 2026,
        then verifies that between=(17:55, 18:05) is interpreted as local times
        (17:55-18:05 BST = 16:55-17:05 UTC), not UTC times.
        """
        # Set fake clock to September 12, 2026 at 18:00 BST (17:00 UTC)
        # Europe/London is UTC+1 during BST (late March to late October)
        time_machine.jump_to_next(month="Sep", day_of_month=12, hour=18, minute=0, second=0)

        # Change state at 18:00 local time (17:00 UTC)
        home_assistant.set_state(self.an_entity, "on")

        # Advance time by 10 minutes (to 18:10 BST = 17:10 UTC)
        time_machine.fast_forward(timedelta(minutes=10))

        # Assert the entity was "on" between 17:55 and 18:05 local time
        # This should succeed because the state change happened at 18:00 local time
        # If the bug exists, this will fail because it will look for the state change
        # between 17:55-18:05 UTC (18:55-19:05 BST), which is in the future
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(time(17, 55), time(18, 5)),
        )

        assert len(entries) > 0
        assert entries[0]["state"] == "on"
