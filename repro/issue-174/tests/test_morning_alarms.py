"""Morning alarm patterns - mirrors full suite's test_morning_alarms.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMorningAlarms:
    def test_alarm_fires_at_7am(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=6, minute=59)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.get_state("sensor.test_time_sensor")
        home_assistant.get_state("sensor.test_time_period")

    def test_alarm_fires_at_7am_weekend(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=7, minute=0)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.times_of_day")

    def test_alarm_sequence(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=6, minute=45)
        home_assistant.get_state("sensor.daylight")
        time_machine.fast_forward(timedelta(minutes=5, seconds=15))
        home_assistant.get_state("sensor.someone_at_home")
        time_machine.fast_forward(timedelta(minutes=10, seconds=15))
        home_assistant.get_state("sensor.heating_preset")

    def test_alarm_media_sequence(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=7, minute=0)
        home_assistant.get_state("sensor.cheap_electricity")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(minutes=2, seconds=15))
        home_assistant.get_state("sensor.precipitation_next_hour")

    def test_alarm_wind_down(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=7, minute=15)
        home_assistant.get_state("sensor.living_room_tv_on")
        time_machine.fast_forward(timedelta(minutes=15, seconds=15))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(minutes=30, seconds=15))
        home_assistant.get_state("sensor.next_alarm")

    def test_alarm_cleanup(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=8, minute=0)
        home_assistant.get_state("sensor.test_time_period")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.times_of_day")
