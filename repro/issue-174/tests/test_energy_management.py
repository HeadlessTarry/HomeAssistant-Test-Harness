"""Energy management patterns - mirrors full suite's test_energy_management.py structure."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestEnergyManagement:
    def test_switches_turn_on_when_cheap_electricity(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=2, minute=0)
        home_assistant.get_state("sensor.cheap_electricity")
        time_machine.fast_forward(timedelta(seconds=45))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(seconds=30))
        home_assistant.get_state("sensor.times_of_day")

    def test_switches_turn_off_when_expensive_electricity(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=8, minute=0)
        home_assistant.get_state("sensor.cheap_electricity")
        time_machine.fast_forward(timedelta(seconds=10))
        home_assistant.get_state("sensor.daylight")
        time_machine.fast_forward(timedelta(seconds=10))
        home_assistant.get_state("sensor.heating_preset")
