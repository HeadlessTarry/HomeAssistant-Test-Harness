"""Integration tests for clock coherence under WebSocket time control.

Home Assistant reads the wall clock through several unrelated routes. Time control is
only sound if they all agree; where they disagree, HA compares a fake timestamp against
a real one and behaves as though hours have passed when they have not.

These are regression tests for issue #178, where a partially applied time offset made
automations fire the instant time moved and left pending delays firing early.

Not covered here: HA's rate limiting of templates that iterate a whole domain, which
the same clock mismatch stalled indefinitely. Exercising it requires a re-render to be
deferred, and whether HA defers a given re-render - and whether it then re-installs the
domain listener - is not deterministic under compressed time. A test for it failed
roughly one run in twelve, so the downstream suite covers that path instead.

Run with: pytest examples/test_time_control_clock_coherence.py -v
"""

from datetime import timedelta

from ha_integration_test_harness import HomeAssistant, TimeMachine


class TestStateTimestampsFollowFakeTime:
    """State timestamps must be stamped on the same clock that now() reports."""

    light = "light.clock_coherence_light"

    def test_last_changed_is_stamped_on_the_fake_clock(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """A state written after a jump records the fake time, not the real time."""
        home_assistant.given_an_entity(self.light, "off")
        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})

        time_machine.fast_forward(timedelta(hours=2))

        # Writing the state again after the jump must stamp it in the fake frame.
        home_assistant.call_action("homeassistant", "turn_off", {"entity_id": self.light})
        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})

        state = home_assistant.get_state(self.light)
        assert state is not None
        fake_now = str(home_assistant.ws_time_get()["timestamp"])
        assert state["last_changed"][:13] == fake_now[:13], f"last_changed {state['last_changed']} is not on the fake clock ({fake_now})"

    def test_a_jump_does_not_rewrite_existing_timestamps(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Advancing time leaves already-recorded timestamps where they were."""
        home_assistant.given_an_entity(self.light, "off")
        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})

        before = home_assistant.get_state(self.light)
        assert before is not None

        time_machine.fast_forward(timedelta(hours=2))

        after = home_assistant.get_state(self.light)
        assert after is not None
        assert after["last_changed"] == before["last_changed"]

    def test_an_automation_comparing_last_changed_to_now_does_not_fire_early(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """A 'on for 3 hours' automation must respect a reset of the entity's timer.

        The automation turns off entities whose last_changed is more than three hours
        before now(). Toggling the light restarts that window, so after a further two
        fake hours it has only been on for two and must stay on.
        """
        home_assistant.given_an_entity(self.light, "off").with_labels(["clock_coherence_auto_off"])

        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})
        time_machine.fast_forward(timedelta(hours=2))

        home_assistant.call_action("homeassistant", "turn_off", {"entity_id": self.light})
        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})
        time_machine.fast_forward(timedelta(hours=2))

        home_assistant.assert_entity_state(self.light, "on")

    def test_the_same_automation_still_fires_once_the_window_is_exceeded(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """The counterpart to the test above: it must still fire when it should."""
        home_assistant.given_an_entity(self.light, "off").with_labels(["clock_coherence_auto_off"])

        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": self.light})
        time_machine.fast_forward(timedelta(hours=3, seconds=15))

        home_assistant.assert_entity_state(self.light, "off")


class TestScheduledCallbacksFollowFakeTime:
    """Timers, delays and time triggers must elapse on the fake clock."""

    def test_an_automation_delay_elapses_after_the_delay_not_before(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """A pending delay must survive a small advance and complete after a large one."""
        home_assistant.given_an_entity("light.clock_coherence_delayed_light", "off")
        home_assistant.call_action("input_button", "press", {"entity_id": "input_button.clock_coherence_delay_trigger"})

        # A one second advance must neither complete the 30 minute delay nor block the
        # response waiting for it.
        time_machine.fast_forward(timedelta(seconds=1))
        home_assistant.assert_entity_state("light.clock_coherence_delayed_light", "off")

        time_machine.fast_forward(timedelta(minutes=30, seconds=15))
        home_assistant.assert_entity_state("light.clock_coherence_delayed_light", "on")

    def test_a_timer_entity_finishes_and_fires_its_event(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """A native HA timer must finish, and automations must see timer.finished."""
        home_assistant.given_an_entity("light.clock_coherence_timer_light", "off")
        home_assistant.call_action("timer", "start", {"entity_id": "timer.test_timer", "duration": "00:05:00"})
        home_assistant.assert_entity_state("timer.test_timer", "active")

        time_machine.fast_forward(timedelta(minutes=5, seconds=15))

        home_assistant.assert_entity_state("timer.test_timer", "idle")
        home_assistant.assert_entity_state("light.clock_coherence_timer_light", "on")

    def test_a_wall_clock_time_trigger_fires_when_time_reaches_it(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """An automation with `trigger: time` fires when fake time arrives at it."""
        home_assistant.given_an_entity("light.clock_coherence_time_light", "off")

        time_machine.jump_to_next(hour=3, minute=33)

        home_assistant.assert_entity_state("light.clock_coherence_time_light", "on")


class TestRepeatedAdvancesDoNotFireEarly:
    """Repeated advances must fire an automation once, when its window is actually up.

    The reported symptom was entities oscillating on/off/on/off within 100ms of a time
    jump. Two defects fed it: state timestamps sat on a different clock from now(), and
    pending deadlines were compared against the *total* accumulated offset rather than
    elapsed time - so once a session had banked an offset, every advance re-fired
    everything scheduled within it.

    Stepping through the window in small advances exercises both. A single advance, as
    the sibling tests use, would not: the accumulated offset only builds up over
    several.
    """

    def test_stepping_through_the_window_fires_the_automation_exactly_once(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """The light holds 'on' for every step under 3h, then turns off crossing it."""
        light = "light.clock_coherence_stepped_light"
        home_assistant.given_an_entity(light, "off").with_labels(["clock_coherence_auto_off"])

        home_assistant.call_action("homeassistant", "turn_on", {"entity_id": light})

        # Five half-hour steps reach 2h30m, still inside the three hour window.
        for _ in range(5):
            time_machine.fast_forward(timedelta(minutes=30))
            home_assistant.assert_entity_state(light, "on")

        # The sixth crosses three hours, so now it must turn off - once.
        time_machine.fast_forward(timedelta(minutes=30, seconds=15))
        home_assistant.assert_entity_state(light, "off")


class TestWebSocketStaysResponsive:
    """Time control must keep replying while Home Assistant has work outstanding.

    The reported symptom was the container going unresponsive during time jumps, seen
    by the test as `TimeMachineError: ... Connection timed out`. The cause was the
    handler waiting for every tracked task before replying: an automation part-way
    through a `delay:` is such a task, and its delay can only elapse when time advances
    again - which the handler is currently blocking.

    Advancing repeatedly in steps smaller than the pending delay keeps a task
    outstanding for the whole test, so every one of these calls has to return on its
    own rather than by waiting the delay out.
    """

    def test_advances_reply_while_an_automation_is_mid_delay(self, home_assistant: HomeAssistant, time_machine: TimeMachine) -> None:
        """Ten advances, all inside a pending 30 minute delay, must each return."""
        light = "light.clock_coherence_delayed_light"
        home_assistant.given_an_entity(light, "off")
        home_assistant.call_action("input_button", "press", {"entity_id": "input_button.clock_coherence_delay_trigger"})

        # Ten one minute steps stay well inside the 30 minute delay, so the automation
        # is still asleep for every one of them.
        for _ in range(10):
            result = home_assistant.ws_time_advance(60.0)
            assert "timestamp" in result

        home_assistant.assert_entity_state(light, "off")

        # And the connection is still usable afterwards.
        assert home_assistant.get_state("sun.sun") is not None
