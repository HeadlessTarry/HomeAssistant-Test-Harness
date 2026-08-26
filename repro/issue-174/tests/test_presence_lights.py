"""Presence light patterns - mirrors full suite's test_presence_lights.py structure."""

from datetime import timedelta

import pytest

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestStudyCeilingLight:
    light_entity = "light.test_light"

    @pytest.fixture(autouse=True)
    def setup(self, home_assistant: HomeAssistant) -> None:
        home_assistant.set_state("binary_sensor.test_pir", "off")
        home_assistant.set_state("binary_sensor.test_occupancy", "off")

    def test_light_turns_off_when_occupancy_off_for_1_minute(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=21, minute=0)
        home_assistant.set_state("binary_sensor.test_pir", "on")
        home_assistant.set_state("binary_sensor.test_occupancy", "on")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.test_time_period")

        home_assistant.set_state("binary_sensor.test_occupancy", "off")
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.times_of_day")

    def test_light_turns_on_immediately_when_pir_fires(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=0)
        home_assistant.get_state(self.light_entity)
        home_assistant.set_state("binary_sensor.test_pir", "on")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.daylight")

    def test_light_turns_on_when_daylight_ends(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=0)
        home_assistant.set_state("binary_sensor.test_occupancy", "on")
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.test_time_sensor")

    def test_light_stays_off_when_room_empty(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=0)
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.heating_preset")

    def test_light_turns_off_when_daylight_returns(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=21, minute=0)
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.someone_at_home")


class TestEnSuiteCeilingLightsNight:
    light_entity = "light.test_light_2"

    @pytest.fixture(autouse=True)
    def setup(self, home_assistant: HomeAssistant) -> None:
        home_assistant.set_state("binary_sensor.test_pir", "off")
        home_assistant.set_state("binary_sensor.test_occupancy", "on")

    def test_light_turns_on_when_presence_detected_at_night(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state(self.light_entity)
        home_assistant.set_state("binary_sensor.test_pir", "on")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.next_alarm")

    def test_light_turns_off_when_occupancy_lost(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=23, minute=0)
        home_assistant.get_state(self.light_entity)
        home_assistant.set_state("binary_sensor.test_occupancy", "off")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.mockupancy_active")


class TestEnSuiteCeilingLightsDay:
    light_entity = "light.test_light_3"

    @pytest.fixture(autouse=True)
    def setup(self, home_assistant: HomeAssistant) -> None:
        home_assistant.set_state("binary_sensor.test_pir", "off")
        home_assistant.set_state("binary_sensor.test_occupancy", "on")

    def test_light_turns_on_when_presence_detected_during_day(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=18, minute=0)
        home_assistant.get_state(self.light_entity)
        home_assistant.set_state("binary_sensor.test_pir", "on")
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.cheap_electricity")


class TestBathroomWakeUpLights:
    light_entity = "light.test_light"

    @pytest.fixture(autouse=True)
    def setup(self, home_assistant: HomeAssistant) -> None:
        pass

    def test_lights_turn_on_when_wake_up_alarm_fires(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=6, minute=30)
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.precipitation_next_hour")

    def test_lights_stay_on_for_300s_after_daylight_returns(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=7, minute=0)
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(minutes=4, seconds=15))
        home_assistant.get_state(self.light_entity)
        time_machine.fast_forward(timedelta(minutes=1, seconds=15))
        home_assistant.get_state(self.light_entity)
        home_assistant.get_state("sensor.living_room_tv_on")
