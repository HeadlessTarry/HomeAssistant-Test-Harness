"""Maintenance patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMaintenance:
    def test_maintenance_window_checks(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=3, minute=0)
        home_assistant.get_state("sensor.cheap_electricity")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.heating_preset")

    def test_maintenance_with_timer_checks(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=4, minute=0)
        home_assistant.get_state("timer.delay_after_restart")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("timer.auto_off_timer")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("timer.pause_timer")
