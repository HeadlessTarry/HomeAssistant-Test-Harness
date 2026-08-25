"""Stress test - rapid successive time jumps to overwhelm the event loop."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestStress:
    def test_rapid_successive_jumps(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for i in range(20):
            time_machine.fast_forward(timedelta(hours=1))
            home_assistant.get_state("sun.sun")
            home_assistant.get_state("sensor.test_time_sensor")
            home_assistant.get_state("sensor.test_time_period")
            home_assistant.get_state("sensor.times_of_day")
            home_assistant.get_state("sensor.daylight")

    def test_large_time_jumps(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for i in range(10):
            time_machine.fast_forward(timedelta(hours=12))
            home_assistant.get_state("sun.sun")
            home_assistant.get_state("sensor.heating_preset")
            home_assistant.get_state("sensor.cheap_electricity")
            home_assistant.get_state("sensor.someone_at_home")
            home_assistant.get_state("sensor.mockupancy_active")

    def test_mixed_jump_pattern(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for i in range(5):
            time_machine.jump_to_next(hour=6, minute=0)
            home_assistant.get_state("sensor.test_time_sensor")
            time_machine.jump_to_next(hour=12, minute=0)
            home_assistant.get_state("sensor.times_of_day")
            time_machine.jump_to_next(hour=18, minute=0)
            home_assistant.get_state("sensor.daylight")
            time_machine.jump_to_next(hour=23, minute=0)
            home_assistant.get_state("sensor.heating_preset")
            time_machine.fast_forward(timedelta(hours=7))
            home_assistant.get_state("sensor.next_alarm")
