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
        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = current_time["timestamp"][11:13]
        current_minute = current_time["timestamp"][14:16]

        # Set up a time window in the past
        start_hour = int(current_hour) - 1 if int(current_hour) > 0 else 23
        start_minute = int(current_minute)
        end_hour = int(current_hour)
        end_minute = int(current_minute)

        # Change state within the window
        home_assistant.set_state(self.an_entity, "on", {"brightness": 255})

        # Advance time past the window
        time_machine.fast_forward(timedelta(minutes=5))

        # Verify the entity was "on" at some point during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(time(start_hour, start_minute), time(end_hour, end_minute)),
        )

        # Verify we got matching entries
        assert len(entries) > 0
        assert entries[0]["state"] == "on"

    def test_full_duration_mode(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test full-duration mode: entity remained in expected state throughout window."""
        home_assistant.set_state(self.an_entity, "on", {"brightness": 255})

        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        start_hour = current_hour
        start_minute = current_minute + 1
        end_minute = current_minute + 3
        end_hour = start_hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour += 1
        if start_minute >= 60:
            start_minute -= 60
            start_hour += 1

        time_machine.fast_forward(timedelta(minutes=1))
        time_machine.fast_forward(timedelta(minutes=3))

        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(time(start_hour, start_minute), time(end_hour, end_minute)),
        )

        assert len(entries) > 0

    def test_attribute_matching(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with attribute matching."""
        home_assistant.set_state(self.an_entity, "on", {"brightness": 128, "color_temp": 4000})

        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        start_hour = current_hour
        start_minute = current_minute + 1
        end_minute = current_minute + 3
        end_hour = start_hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour += 1
        if start_minute >= 60:
            start_minute -= 60
            start_hour += 1

        time_machine.fast_forward(timedelta(minutes=1))
        time_machine.fast_forward(timedelta(minutes=3))

        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(time(start_hour, start_minute), time(end_hour, end_minute)),
            expected_attributes={"brightness": 128},
        )

        assert len(entries) > 0
        assert entries[0]["attributes"]["brightness"] == 128

    def test_predicate_state(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with predicate function for state."""
        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        # Define a window
        start_hour = current_hour
        start_minute = current_minute + 1
        end_minute = current_minute + 3

        # Advance to the start of the window
        time_machine.fast_forward(timedelta(minutes=1))

        # Set entity to a numeric state
        home_assistant.set_state(self.an_entity, "42")

        # Advance time
        time_machine.fast_forward(timedelta(minutes=3))

        # Verify entity state satisfied a predicate during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            lambda s: s.isdigit() and int(s) > 40,
            between=(time(start_hour, start_minute), time(start_hour, end_minute)),
        )

        assert len(entries) > 0
        assert int(entries[0]["state"]) > 40

    def test_predicate_attribute(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with predicate function for attributes."""
        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        # Define a window
        start_hour = current_hour
        start_minute = current_minute + 1
        end_minute = current_minute + 3

        # Advance to the start of the window
        time_machine.fast_forward(timedelta(minutes=1))

        # Set entity with attributes
        home_assistant.set_state(self.an_entity, "on", {"brightness": 200})

        # Advance time
        time_machine.fast_forward(timedelta(minutes=3))

        # Verify entity attributes satisfied a predicate during the window
        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            "on",
            between=(time(start_hour, start_minute), time(start_hour, end_minute)),
            expected_attributes={"brightness": lambda v: v is not None and v >= 150},
        )

        assert len(entries) > 0
        assert entries[0]["attributes"]["brightness"] >= 150

    def test_attribute_only_check(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test retrospective assertion with attribute-only check (no state check)."""
        home_assistant.set_state(self.an_entity, "on", {"brightness": 100})

        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        start_hour = current_hour
        start_minute = current_minute + 1
        end_minute = current_minute + 3
        if start_minute >= 60:
            start_minute -= 60
            start_hour += 1
        end_hour = start_hour
        if end_minute >= 60:
            end_minute -= 60
            end_hour += 1

        time_machine.fast_forward(timedelta(minutes=1))
        time_machine.fast_forward(timedelta(minutes=3))

        entries = home_assistant.assert_entity_was_in_state(
            self.an_entity,
            None,
            between=(time(start_hour, start_minute), time(end_hour, end_minute)),
            expected_attributes={"brightness": 100},
        )

        assert len(entries) > 0

    def test_failure_no_history(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that assertion fails when no history exists in the window."""
        # Create a fresh entity that has no history
        fresh_entity = "sensor.fresh_entity"
        home_assistant.given_an_entity(fresh_entity, state="initial")

        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        # Define a window in the far past (before the entity was created)
        start_hour = (current_hour - 5) % 24
        start_minute = current_minute
        end_hour = (current_hour - 4) % 24
        end_minute = current_minute

        # Advance time
        time_machine.fast_forward(timedelta(minutes=1))

        # This should fail because no state changes occurred in that window
        with pytest.raises(AssertionError, match="No state changes recorded|was not in state"):
            home_assistant.assert_entity_was_in_state(
                fresh_entity,
                "on",
                between=(time(start_hour, start_minute), time(end_hour, end_minute)),
            )

    def test_failure_state_not_matched(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that assertion fails when state doesn't match."""
        # Set entity to "off"
        home_assistant.set_state(self.an_entity, "off")

        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        # Define a window
        start_hour = current_hour
        start_minute = current_minute
        end_minute = current_minute + 2

        # Advance time
        time_machine.fast_forward(timedelta(minutes=5))

        # This should fail because entity was "off", not "on"
        with pytest.raises(AssertionError, match="was not in state"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
                between=(time(start_hour, start_minute), time(start_hour, end_minute)),
            )

    def test_failure_full_duration_not_met(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that full-duration assertion fails when state changes during window."""
        # Set entity to "on"
        home_assistant.set_state(self.an_entity, "on")

        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        # Define a window
        start_hour = current_hour
        start_minute = current_minute
        end_minute = current_minute + 5

        # Change state partway through the window
        time_machine.fast_forward(timedelta(minutes=2))
        home_assistant.set_state(self.an_entity, "off")

        # Advance past the window
        time_machine.fast_forward(timedelta(minutes=5))

        # This should fail because entity didn't remain "on" for the full duration
        with pytest.raises(AssertionError, match="was not in state"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                "on",
                between=(time(start_hour, start_minute), time(start_hour, end_minute)),
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
        # Record current time
        current_time = home_assistant.ws_time_get()
        current_hour = int(current_time["timestamp"][11:13])
        current_minute = int(current_time["timestamp"][14:16])

        with pytest.raises(ValueError, match="At least one of expected_state or expected_attributes"):
            home_assistant.assert_entity_was_in_state(
                self.an_entity,
                None,
                between=(time(current_hour, current_minute), time(current_hour, current_minute + 5)),
            )
