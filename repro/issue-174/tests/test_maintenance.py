"""Maintenance patterns - mirrors full suite's test_homeassistant_maintenance.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMaintenance:
    delay_timer = "timer.delay_after_restart"

    def test_delay_timer_triggered_after_restart(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "active")
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(seconds=45))
        home_assistant.get_state("sensor.test_time_period")
        time_machine.fast_forward(timedelta(seconds=30))
        home_assistant.get_state("sensor.times_of_day")
        home_assistant.get_state("sensor.daylight")
