"""Study/gaming sign patterns - mirrors full suite's test_study_gaming_sign.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestStudyGamingSign:
    def test_evening_schedule(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=19, minute=59)
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.get_state("sensor.test_time_period")
        home_assistant.get_state("sensor.times_of_day")

    def test_late_evening_schedule(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=5)
        home_assistant.get_state("sensor.daylight")
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.get_state("sensor.heating_preset")

    def test_night_transition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=21, minute=15)
        home_assistant.get_state("sensor.someone_at_home")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.cheap_electricity")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.next_alarm")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.mockupancy_active")

    def test_late_night_transition(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=22, minute=20)
        home_assistant.get_state("sensor.precipitation_next_hour")
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state("sensor.living_room_tv_on")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state("sensor.test_time_sensor")
