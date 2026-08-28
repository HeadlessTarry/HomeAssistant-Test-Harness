"""Example tests demonstrating TimeMachine usage."""

from datetime import datetime, timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestTimeMachine:

    def parse_datetime(self, iso_string: str) -> datetime:
        """Parse ISO 8601 datetime string and strip timezone to get naive UTC datetime.

        This treats all timestamps as UTC (matching container timezone) without conversion,
        consistent with TimeMachine's behavior.

        Args:
            iso_string: ISO 8601 formatted datetime string (e.g., "2026-02-02T15:30:00+00:00").

        Returns:
            Naive datetime object in UTC with timezone info stripped for comparison.
        """
        return datetime.fromisoformat(iso_string).replace(tzinfo=None)

    def assert_datetime_is_approx(self, home_assistant: HomeAssistant, expected: datetime, tolerance_in_seconds: int = 5) -> None:
        """Helper to assert that the current datetime is close to expected (within a few seconds)."""

        home_assistant.assert_entity_state("sensor.current_datetime", lambda current_state: abs(self.parse_datetime(current_state) - expected) <= timedelta(seconds=tolerance_in_seconds))

    def test_fast_forward_by_seconds(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing time by seconds."""
        # Query current time before advancement
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Fast forward by 30 seconds
        delta = timedelta(seconds=30)
        time_machine.fast_forward(delta)

        # Calculate expected time and verify
        expected_dt = before_dt + delta
        self.assert_datetime_is_approx(home_assistant, expected_dt)

    def test_fast_forward_by_days(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing time by days."""
        # Query current time before advancement
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Fast forward by 2 days
        delta = timedelta(days=2)
        time_machine.fast_forward(delta)

        # Calculate expected time and verify
        expected_dt = before_dt + delta
        self.assert_datetime_is_approx(home_assistant, expected_dt)

    def test_fast_forward_by_multiple_units(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing time using multiple time units."""
        # Query current time before advancement
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Fast forward by 1 day, 4 hours, 30 minutes
        delta = timedelta(days=1, hours=4, minutes=30)
        time_machine.fast_forward(delta)

        # Calculate expected time
        expected_dt = before_dt + delta
        self.assert_datetime_is_approx(home_assistant, expected_dt)

    def test_jump_to_next_weekday(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test jumping to next occurrence of a specific weekday."""
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Jump to next Monday (preserves current time of day)
        time_machine.jump_to_next(day="Monday")

        # Verify we advanced to a Monday
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt >= before_dt  # Time moved forward
        assert after_dt.weekday() == 0  # Monday is 0
        # Verify time components preserved (within 2 seconds to account for test execution time)
        before_seconds = before_dt.hour * 3600 + before_dt.minute * 60 + before_dt.second
        after_seconds = after_dt.hour * 3600 + after_dt.minute * 60 + after_dt.second
        time_diff = abs(after_seconds - before_seconds)
        assert time_diff < 2, f"Time components drifted by {time_diff} seconds"

    def test_jump_to_next_month(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test jumping to next occurrence of a specific month."""
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Compute the actual next calendar month (handle December wrap-around)
        if before_dt.month == 12:
            expected_month = 1
            expected_year = before_dt.year + 1
        else:
            expected_month = before_dt.month + 1
            expected_year = before_dt.year

        # Use the expected month/year to derive the month name for jump_to_next
        next_month_dt = datetime(expected_year, expected_month, 1)
        next_month_name = next_month_dt.strftime("%b")

        # Jump to next month (preserves current day and time)
        time_machine.jump_to_next(month=next_month_name)

        # Verify we advanced to the expected next month
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt >= before_dt  # Time moved forward
        assert after_dt.month == expected_month  # Moved to next calendar month
        # Verify time components preserved (hour, minute, second)
        assert after_dt.time() == before_dt.time()

    def test_jump_to_first_of_month(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test jumping to the 1st of the next month."""
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Jump to 1st of next month (preserves time)
        time_machine.jump_to_next(day_of_month=1)

        # Verify we're on the 1st of a month
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt >= before_dt  # Time moved forward
        assert after_dt.day == 1  # 1st of the month
        # Verify time components preserved (hour, minute, second)
        assert after_dt.time() == before_dt.time()

    def test_jump_to_next_with_time(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test jumping to next Monday at specific time."""
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Jump to next Monday at 10:00:00
        time_machine.jump_to_next(day="Monday", hour=10, minute=0, second=0)

        # Verify we're on Monday at exactly 10:00:00
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt >= before_dt  # Time moved forward
        assert after_dt.weekday() == 0  # Monday is 0
        # Time components set to specified values
        assert after_dt.hour == 10
        assert after_dt.minute == 0
        assert after_dt.second == 0

    def test_jump_to_next_hour_moves_to_next_day_when_already_past_hour_specified(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test jumping to next hour when current fake time is already past the specified hour."""
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Jump to next hour that is guaranteed to be in the past relative to current time
        if before_dt.hour > 0:
            earlier_hour = before_dt.hour - 1
        else:
            # At or near midnight: use 00:00, which is earlier in the same day than almost any realistic test time
            earlier_hour = 0
        time_machine.jump_to_next(hour=earlier_hour)

        # Verify we rollover to the next day at the specified hour
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt >= before_dt  # Time moved forward
        assert after_dt.date() > before_dt.date()  # Date advanced
        assert after_dt.hour == earlier_hour  # Hour set to specified value

    def test_jump_to_next_constraint_sequence(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test constraint resolution order: month -> day_of_month -> weekday -> time.

        Example: If current fake time is Tue Jan 31 14:30:00
        Calling jump_to_next(month="Feb", day_of_month=1, day="Monday", hour=10)

        Step 1: Jump to February -> Feb 1 14:30:00
        Step 2: Set day_of_month=1 -> Feb 1 14:30:00 (already on 1st)
        Step 3: Advance to next Monday -> Feb 3 14:30:00 (assuming Feb 1 was Saturday)
        Step 4: Set hour=10 -> Feb 3 10:30:00

        Note: Minutes/seconds preserved as they weren't specified
        """
        # Query current time before jump
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])
        before_month = before_dt.month
        next_month_name = (before_dt + timedelta(weeks=4)).strftime("%b")

        # Jump to next month, 1st, then next Monday, at 10:XX:XX
        time_machine.jump_to_next(month=next_month_name, day_of_month=1, day="Monday", hour=10)

        # Verify all constraints applied
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        expected_month = 1 if before_month == 12 else before_month + 1
        expected_year = before_dt.year + 1 if before_month == 12 else before_dt.year
        assert after_dt.year == expected_year  # Year should advance when wrapping from December to January
        assert after_dt.month == expected_month  # Next month with wrap-around
        assert after_dt.weekday() == 0  # Monday
        assert after_dt.hour == 10
        assert after_dt >= before_dt  # Time moved forward
        # Minutes/seconds should be preserved from before the jump
        assert after_dt.minute == before_dt.minute
        assert after_dt.second == before_dt.second

    def test_jump_to_next_preserves_unspecified_time_components(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test that unspecified time components are preserved from current fake time."""
        # Query current time
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # First advance to a specific time with distinct minute/second values
        time_machine.fast_forward(timedelta(hours=14, minutes=37, seconds=42))

        # Get time after fast_forward to capture the specific time components
        after_ff_state = home_assistant.get_state("sensor.current_datetime")
        after_ff_dt = self.parse_datetime(after_ff_state["state"])

        # Jump to next Wednesday - hour/minute/second should be preserved
        time_machine.jump_to_next(day="Wednesday")

        # Verify Wednesday and that time components were preserved
        after_state = home_assistant.get_state("sensor.current_datetime")
        after_dt = self.parse_datetime(after_state["state"])
        assert after_dt.weekday() == 2  # Wednesday is 2
        assert after_dt >= before_dt  # Time moved forward
        # Time components should match the time after fast_forward (within 2 seconds)
        ff_seconds = after_ff_dt.hour * 3600 + after_ff_dt.minute * 60 + after_ff_dt.second
        after_seconds = after_dt.hour * 3600 + after_dt.minute * 60 + after_dt.second
        time_diff = abs(after_seconds - ff_seconds)
        assert time_diff < 2, f"Time components drifted by {time_diff} seconds"

    def test_advance_to_sunrise(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to next sunrise."""
        # Ensure that we're starting before sunrise
        time_machine.jump_to_next(hour=3)
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

        # Query sun state to get next_rising time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_rising = self.parse_datetime(sun_state_before["attributes"]["next_rising"])

        # Advance to next sunrise
        time_machine.advance_to_preset("sunrise")

        # Verify current time matches sunrise
        self.assert_datetime_is_approx(home_assistant, next_rising)

        # Verify sun is above horizon (with polling to handle state transition delay)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

    def test_advance_to_before_sunrise(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to 30 minutes before next sunrise."""
        # Ensure that we're starting before sunrise
        time_machine.jump_to_next(hour=3)
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

        # Query sun state to get next_rising time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_rising = self.parse_datetime(sun_state_before["attributes"]["next_rising"])

        # Advance to 30 minutes before next sunrise
        offset = timedelta(minutes=-30)
        time_machine.advance_to_preset("sunrise", offset)

        # Verify current time is 30 minutes before sunrise
        expected_dt = next_rising + offset
        self.assert_datetime_is_approx(home_assistant, expected_dt)

        # Verify sun is below horizon (30 min before sunrise = nighttime)
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

    def test_advance_to_after_sunrise(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to 30 minutes after next sunrise."""
        # Ensure that we're starting before sunrise
        time_machine.jump_to_next(hour=3)
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

        # Query sun state to get next_rising time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_rising = self.parse_datetime(sun_state_before["attributes"]["next_rising"])

        # Advance to 30 minutes after next sunrise
        offset = timedelta(minutes=30)
        time_machine.advance_to_preset("sunrise", offset)

        # Verify current time is 30 minutes after sunrise
        expected_dt = next_rising + offset
        self.assert_datetime_is_approx(home_assistant, expected_dt)

        # Verify sun is above horizon (30 min after sunrise = daytime)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

    def test_advance_to_sunset(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to next sunset."""
        # Ensure that we're starting before sunset
        time_machine.jump_to_next(hour=15)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

        # Query sun state to get next_setting time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_setting = self.parse_datetime(sun_state_before["attributes"]["next_setting"])

        # Advance to next sunset
        time_machine.advance_to_preset("sunset")

        # Verify current time matches sunset
        self.assert_datetime_is_approx(home_assistant, next_setting)

        # Verify sun is below horizon (with polling to handle state transition delay)
        # Sun setting can take minutes to fully transition to below_horizon, so we fast
        # forward a number of minutes first
        time_machine.fast_forward(timedelta(minutes=10))
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

    def test_advance_to_before_sunset(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to 1 hour before next sunset."""
        # Ensure that we're starting before sunset
        time_machine.jump_to_next(hour=15)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

        # Query sun state to get next_setting time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_setting = self.parse_datetime(sun_state_before["attributes"]["next_setting"])

        # Advance to 30 minutes before next sunset
        offset = timedelta(minutes=-30)
        time_machine.advance_to_preset("sunset", offset)

        # Verify current time is 30 minutes before sunset
        expected_dt = next_setting + offset
        self.assert_datetime_is_approx(home_assistant, expected_dt)

        # Verify sun is above horizon (30 minutes before sunset = still daytime)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

    def test_advance_to_after_sunset(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing to 1 hour after next sunset."""
        # Ensure that we're starting before sunset
        time_machine.jump_to_next(hour=15)
        home_assistant.assert_entity_state("sun.sun", "above_horizon")

        # Query sun state to get next_setting time
        sun_state_before = home_assistant.get_state("sun.sun")
        next_setting = self.parse_datetime(sun_state_before["attributes"]["next_setting"])

        # Advance to 30 minutes after next sunset
        offset = timedelta(minutes=30)
        time_machine.advance_to_preset("sunset", offset)

        # Verify current time is 30 minutes after sunset
        expected_dt = next_setting + offset
        self.assert_datetime_is_approx(home_assistant, expected_dt)

        # Verify sun is below horizon (30 minutes after sunset = nighttime)
        home_assistant.assert_entity_state("sun.sun", "below_horizon")

    def test_fast_forward_by_one_year(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Test advancing time by one year to verify long-lived token works beyond 90-day refresh token limit."""
        # Query current time before advancement
        before_state = home_assistant.get_state("sensor.current_datetime")
        before_dt = self.parse_datetime(before_state["state"])

        # Fast forward by 1 year
        delta = timedelta(days=365)
        time_machine.fast_forward(delta)

        # Calculate expected time and verify
        expected_dt = before_dt + delta
        self.assert_datetime_is_approx(home_assistant, expected_dt)
