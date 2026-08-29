"""Integration tests for WebSocket-based time control.

Tests the ha_test_harness/time/* WebSocket commands: time/set, time/advance, time/get.
Verifies that time offset is applied correctly to HA's time functions and that
scheduled timers are fired when time is advanced.

Run with: pytest examples/test_websocket_time_control.py -v
"""

from datetime import datetime, timedelta, timezone

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestWebSocketTimeControl:
    """Integration tests for WebSocket time control."""

    def parse_datetime(self, iso_string: str) -> datetime:
        """Parse ISO 8601 datetime string and strip timezone to get naive UTC datetime."""
        return datetime.fromisoformat(iso_string).replace(tzinfo=None)

    def get_fake_time(self, home_assistant: HomeAssistant) -> datetime:
        """Get the current fake time from the WebSocket API."""
        result = home_assistant.ws_time_get()
        return self.parse_datetime(result["timestamp"])

    def test_time_get_returns_current_fake_time(self, home_assistant: HomeAssistant) -> None:
        """Test that time/get returns the current fake time."""
        result = home_assistant.ws_time_get()
        assert "timestamp" in result
        assert "offset_seconds" in result
        fake_time = datetime.fromisoformat(result["timestamp"])
        assert fake_time.tzinfo is not None

    def test_time_set_changes_fake_time(self, home_assistant: HomeAssistant) -> None:
        """Test that time/set changes the fake time to an absolute value."""
        target = datetime(2027, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = home_assistant.ws_time_set(target.isoformat())

        assert "timestamp" in result
        fake_time = self.parse_datetime(result["timestamp"])
        assert fake_time.year == 2027
        assert fake_time.month == 6
        assert fake_time.day == 15
        assert fake_time.hour == 12

    def test_time_advance_moves_time_forward(self, home_assistant: HomeAssistant) -> None:
        """Test that time/advance moves time forward by the specified seconds."""
        before_time = self.get_fake_time(home_assistant)

        home_assistant.ws_time_advance(3600)

        after_time = self.get_fake_time(home_assistant)

        delta = after_time - before_time
        assert abs(delta.total_seconds() - 3600) < 5

    def test_time_advance_accepts_negative(self, home_assistant: HomeAssistant) -> None:
        """Test that time/advance accepts negative values (moves time backward)."""
        before_time = self.get_fake_time(home_assistant)

        home_assistant.ws_time_advance(-3600)

        after_time = self.get_fake_time(home_assistant)

        delta = after_time - before_time
        assert abs(delta.total_seconds() + 3600) < 5

    def test_time_set_affects_ha_sensor(self, home_assistant: HomeAssistant) -> None:
        """Test that setting time via WebSocket affects HA's sensor.current_datetime."""
        target = datetime(2028, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        home_assistant.ws_time_set(target.isoformat())

        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            lambda s: s is not None and datetime.fromisoformat(s).year == 2028,
            timeout=10,
        )

    def test_time_advance_affects_ha_sensor(self, home_assistant: HomeAssistant) -> None:
        """Test that advancing time via WebSocket affects HA's sensor.current_datetime."""
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_time = self.parse_datetime(before_state["state"])

        home_assistant.ws_time_advance(7200)

        def _check_advanced(s: str) -> bool:
            if s is None:
                return False
            after_time = self.parse_datetime(s)
            delta = (after_time - before_time).total_seconds()
            return abs(delta - 7200) < 10

        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            _check_advanced,
            timeout=10,
        )

    def test_time_machine_fast_forward_uses_websocket(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that TimeMachine.fast_forward uses WebSocket time/advance."""
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_time = self.parse_datetime(before_state["state"])

        time_machine.fast_forward(timedelta(hours=3))

        def _check_advanced(s: str) -> bool:
            if s is None:
                return False
            after_time = self.parse_datetime(s)
            delta = (after_time - before_time).total_seconds()
            return abs(delta - 10800) < 10

        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            _check_advanced,
            timeout=10,
        )

    def test_time_machine_jump_to_next_uses_websocket(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that TimeMachine.jump_to_next uses WebSocket time/set."""
        time_machine.jump_to_next(day="Monday")

        def _check_monday(s: str) -> bool:
            if s is None:
                return False
            dt = self.parse_datetime(s)
            return dt.weekday() == 0

        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            _check_monday,
            timeout=10,
        )

    def test_rapid_time_jumps_stable(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that rapid time jumps don't cause HA instability."""
        for i in range(5):
            time_machine.fast_forward(timedelta(hours=1))
            state = home_assistant.get_state("sensor.current_datetime")
            assert state is not None, f"HA unresponsive after time jump #{i + 1}"

    def test_large_time_jump_stable(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that a large time jump doesn't cause HA instability."""
        time_machine.fast_forward(timedelta(days=30))
        state = home_assistant.get_state("sensor.current_datetime")
        assert state is not None, "HA unresponsive after large time jump"

    def test_timer_fires_when_time_advanced(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that scheduled timers/automations fire when time is advanced past their trigger time."""
        # Get current time
        current_state = home_assistant.get_state("sensor.current_datetime")
        current_dt = self.parse_datetime(current_state["state"])

        # Advance by 30 seconds
        time_machine.fast_forward(timedelta(seconds=30))

        # Verify the sensor updated (the sensor.current_datetime updates every second via time_pattern trigger)
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])

        # Verify time actually advanced
        assert after_dt > current_dt, "Time should have advanced"
        # Verify it advanced by approximately the expected amount (30 seconds)
        delta = (after_dt - current_dt).total_seconds()
        assert 28 <= delta <= 32, f"Time should have advanced by ~30 seconds, but advanced by {delta}"

    def test_timezone_aware_time_setting(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that time can be set with timezone-aware datetimes."""
        # The target is derived from the current fake time rather than hard-coded so
        # that it stays ahead of it. Time is session-scoped and only moves forward, and
        # HA's recurring time listeners are armed against absolute targets: moving the
        # clock backwards leaves them armed in the future, so entities driven by a
        # time_pattern trigger (such as sensor.current_datetime) would legitimately
        # keep reporting their last value.
        target_utc = (self.get_fake_time(home_assistant) + timedelta(days=365)).replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        home_assistant.ws_time_set(target_utc.isoformat())

        # Verify the time was set correctly
        state = home_assistant.get_state("sensor.current_datetime")
        sensor_time = self.parse_datetime(state["state"])
        assert sensor_time.year == target_utc.year
        assert sensor_time.month == target_utc.month
        assert sensor_time.day == target_utc.day
        assert sensor_time.hour == target_utc.hour

    def test_large_time_jump_across_months(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that large time jumps across month boundaries work correctly."""
        # Set time to end of January
        target = datetime(2027, 1, 31, 23, 0, 0, tzinfo=timezone.utc)
        home_assistant.ws_time_set(target.isoformat())

        # Jump forward 2 days (should cross into March)
        time_machine.fast_forward(timedelta(days=2))

        # Verify we're in March
        state = home_assistant.get_state("sensor.current_datetime")
        sensor_time = self.parse_datetime(state["state"])
        assert sensor_time.month == 2  # February (2027 is not a leap year)
        assert sensor_time.day == 2
