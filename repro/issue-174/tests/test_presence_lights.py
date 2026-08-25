"""Presence light patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestPresenceLights:
    def test_presence_lights_daytime(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=10, minute=0)
        home_assistant.get_state("sensor.daylight")
        home_assistant.get_state("light.test_light")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.times_of_day")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.someone_at_home")

    def test_presence_lights_evening(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=18, minute=0)
        home_assistant.get_state("sensor.daylight")
        home_assistant.get_state("light.test_light")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.living_room_tv_on")

    def test_presence_lights_night(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state("sensor.daylight")
        home_assistant.get_state("light.test_light")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.someone_at_home")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.mockupancy_active")

    def test_presence_lights_multiple_lights(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=19, minute=0)
        home_assistant.get_state("light.test_light")
        home_assistant.get_state("light.test_light_2")
        home_assistant.get_state("light.test_light_3")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.heating_preset")

    def test_presence_lights_dawn_transitions(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for hour in [5, 6, 7, 8]:
            time_machine.jump_to_next(hour=hour, minute=30)
            home_assistant.get_state("sensor.daylight")
            home_assistant.get_state("sensor.test_time_period")
