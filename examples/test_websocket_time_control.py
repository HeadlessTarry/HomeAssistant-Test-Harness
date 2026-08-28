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
        before_result = home_assistant.ws_time_get()
        before_time = self.parse_datetime(before_result["timestamp"])

        home_assistant.ws_time_advance(3600)

        after_result = home_assistant.ws_time_get()
        after_time = self.parse_datetime(after_result["timestamp"])

        delta = after_time - before_time
        assert abs(delta.total_seconds() - 3600) < 5

    def test_time_advance_accepts_negative(self, home_assistant: HomeAssistant) -> None:
        """Test that time/advance accepts negative values (moves time backward)."""
        before_result = home_assistant.ws_time_get()
        before_time = self.parse_datetime(before_result["timestamp"])

        home_assistant.ws_time_advance(-3600)

        after_result = home_assistant.ws_time_get()
        after_time = self.parse_datetime(after_result["timestamp"])

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

    def test_temp_set_time_allows_backward_time(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that temp_set_time allows setting time to a past value."""
        far_future = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        home_assistant.ws_time_set(far_future.isoformat())

        past_target = datetime(2025, 6, 15, 12, 0, 0)
        time_machine.temp_set_time(past_target)

        def _check_past(s: str) -> bool:
            if s is None:
                return False
            dt = self.parse_datetime(s)
            return dt.year == 2025 and dt.month == 6

        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            _check_past,
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
