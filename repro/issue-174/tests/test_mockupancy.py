"""Mockupancy (simulated occupancy) patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMockupancy:
    def test_mockupancy_activates_in_evening(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=16, minute=0)
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.jump_to_next(hour=17, minute=0)
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.living_room_tv_on")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.mockupancy_active")

    def test_mockupancy_deactivates_at_night(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=22, minute=0)
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.someone_at_home")

    def test_mockupancy_with_lights(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=17, minute=30)
        home_assistant.get_state("light.test_light")
        home_assistant.get_state("sensor.mockupancy_active")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.times_of_day")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.daylight")
