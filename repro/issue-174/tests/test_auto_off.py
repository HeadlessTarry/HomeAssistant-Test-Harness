"""Auto-off patterns - mirrors full suite's test_auto_off.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestAutoOff:
    light_entity = "light.test_light"
    light_entity_2 = "light.test_light_2"
    delay_timer = "timer.delay_after_restart"

    def test_turns_off_after_3_hours(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(hours=3, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.test_time_period")

    def test_timer_resets_on_toggle(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=8, minute=0)
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(hours=1, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.times_of_day")

    def test_max_duration_only_turns_off_exceeded_entity(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(hours=3, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state(self.light_entity_2)
        home_assistant.get_state("sensor.daylight")

    def test_turns_off_at_night(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "idle")
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.heating_preset")

    def test_turns_off_when_nobody_home(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "idle")
        time_machine.fast_forward(timedelta(minutes=5, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.someone_at_home")

    def test_does_not_turn_off_when_guests_staying(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "idle")
        time_machine.fast_forward(timedelta(minutes=5, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.cheap_electricity")

    def test_does_not_fire_on_startup(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "active")
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(minutes=5, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.next_alarm")

    def test_switch_turns_off_at_night(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        home_assistant.set_state(self.delay_timer, "idle")
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state("sensor.test_time_sensor")

    def test_switch_turns_off_after_max_duration(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.fast_forward(timedelta(hours=3, seconds=15))
        home_assistant.get_state("sensor.mockupancy_active")
