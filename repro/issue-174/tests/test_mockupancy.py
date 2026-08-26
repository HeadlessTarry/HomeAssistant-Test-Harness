"""Mockupancy patterns - mirrors full suite's test_mockupancy_lights.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMockupancyLights:
    def test_evening_mockupancy(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=17, minute=15)
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(minutes=20, seconds=15))
        home_assistant.get_state("sensor.test_time_period")

    def test_late_afternoon_mockupancy(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(minutes=7, seconds=15))
        home_assistant.get_state("sensor.times_of_day")
        home_assistant.get_state("sensor.daylight")

    def test_dusk_mockupancy(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=18, minute=45)
        home_assistant.get_state("sensor.heating_preset")
        time_machine.fast_forward(timedelta(minutes=10, seconds=15))
        home_assistant.get_state("sensor.someone_at_home")

    def test_evening_mockupancy_2(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(minutes=45, seconds=15))
        home_assistant.get_state("sensor.cheap_electricity")
        home_assistant.get_state("sensor.next_alarm")

    def test_night_mockupancy(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=15)
        home_assistant.get_state("sensor.precipitation_next_hour")
        time_machine.fast_forward(timedelta(minutes=15, seconds=15))
        home_assistant.get_state("sensor.living_room_tv_on")

    def test_late_evening_mockupancy(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(minutes=8, seconds=15))
        home_assistant.get_state("sensor.test_time_sensor")
        home_assistant.get_state("sensor.mockupancy_active")
