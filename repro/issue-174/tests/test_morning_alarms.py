"""Morning alarm patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestMorningAlarms:
    def test_morning_alarm_triggers(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=6, minute=0)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.jump_to_next(hour=7, minute=0)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.fast_forward(timedelta(minutes=30))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(minutes=30))
        home_assistant.get_state("sensor.someone_at_home")

    def test_evening_alarm_triggers(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=18, minute=0)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.jump_to_next(hour=19, minute=30)
        home_assistant.get_state("sensor.next_alarm")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.heating_preset")

    def test_alarm_transitions_through_day(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for hour in [6, 9, 12, 15, 18, 21]:
            time_machine.jump_to_next(hour=hour, minute=0)
            home_assistant.get_state("sensor.next_alarm")
            home_assistant.get_state("sensor.test_time_period")
