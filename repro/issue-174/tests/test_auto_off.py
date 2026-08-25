"""Auto-off timer patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestAutoOff:
    def test_auto_off_timer_triggers(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=10, minute=0)
        home_assistant.get_state("timer.auto_off_timer")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.times_of_day")

    def test_auto_off_with_light_on(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=14, minute=0)
        home_assistant.get_state("light.test_light")
        time_machine.fast_forward(timedelta(hours=3))
        home_assistant.get_state("sensor.daylight")
        time_machine.fast_forward(timedelta(minutes=30))
        home_assistant.get_state("sensor.cheap_electricity")

    def test_multiple_timer_checks(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for hour in [8, 12, 16, 20]:
            time_machine.jump_to_next(hour=hour, minute=0)
            home_assistant.get_state("timer.delay_after_restart")
            home_assistant.get_state("timer.pause_timer")
            home_assistant.get_state("sensor.heating_preset")
