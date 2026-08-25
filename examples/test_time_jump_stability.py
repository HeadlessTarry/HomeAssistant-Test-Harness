"""Minimal reproduction for issue #174: HA unresponsive after time jumps.

This test performs multiple rapid time jumps followed by immediate API calls.
Without defensive stabilization, HA can become unresponsive after libfaketime
time jumps due to asyncio quirks in the HA event loop.

Run with: pytest examples/test_time_jump_stability.py -v
"""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestTimeJumpStability:
    """Reproduction tests for issue #174."""

    def test_rapid_time_jumps_then_api_call(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Perform multiple rapid time jumps then immediately call the API.

        Without stabilization, this test has ~36% chance of failure because
        HA's asyncio event loop can stall after libfaketime time jumps.
        """
        for i in range(5):
            time_machine.fast_forward(timedelta(hours=1))
            state = home_assistant.get_state("sensor.current_datetime")
            assert state is not None, f"HA unresponsive after time jump #{i + 1}"

    def test_large_time_jump_then_api_call(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Perform a large time jump then immediately call the API."""
        time_machine.fast_forward(timedelta(days=7))
        state = home_assistant.get_state("sensor.current_datetime")
        assert state is not None, "HA unresponsive after large time jump"

    def test_time_jump_then_entity_state_assertion(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Perform a time jump then assert entity state (which polls)."""
        time_machine.fast_forward(timedelta(hours=2))
        home_assistant.assert_entity_state(
            "sensor.current_datetime",
            lambda s: s is not None,
            timeout=10,
        )

    def test_time_jump_then_set_state(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Perform a time jump then set entity state."""
        time_machine.fast_forward(timedelta(hours=1))
        home_assistant.set_state("sensor.test_stability", "test_value")
        state = home_assistant.get_state("sensor.test_stability")
        assert state is not None
        assert state["state"] == "test_value"

    def test_multiple_time_jumps_with_various_api_calls(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Stress test: multiple time jumps interleaved with various API operations."""
        for i in range(3):
            time_machine.fast_forward(timedelta(minutes=30))

            get_state = home_assistant.get_state("sensor.current_datetime")
            assert get_state is not None, f"get_state failed on iteration {i + 1}"

            config = home_assistant.get_config()
            assert config is not None, f"get_config failed on iteration {i + 1}"

            home_assistant.set_state(f"sensor.stability_test_{i}", "ok")
            state = home_assistant.get_state(f"sensor.stability_test_{i}")
            assert state is not None, f"set_state/get_state failed on iteration {i + 1}"
