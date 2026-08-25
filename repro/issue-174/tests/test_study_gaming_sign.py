"""Study/gaming sign patterns."""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestStudyGamingSign:
    def test_study_gaming_sign_daytime(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=9, minute=0)
        home_assistant.get_state("sensor.someone_at_home")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.test_time_sensor")
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.get_state("sensor.times_of_day")

    def test_study_gaming_sign_evening(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        time_machine.jump_to_next(hour=20, minute=0)
        home_assistant.get_state("sensor.someone_at_home")
        home_assistant.get_state("sensor.living_room_tv_on")
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.get_state("sensor.mockupancy_active")

    def test_study_gaming_sign_transitions(
        self,
        home_assistant: HomeAssistant,
        time_machine: TimeMachine,
    ) -> None:
        for hour in [7, 10, 13, 16, 19, 22]:
            time_machine.jump_to_next(hour=hour, minute=0)
            home_assistant.get_state("sensor.someone_at_home")
            home_assistant.get_state("sensor.test_time_period")
