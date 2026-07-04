"""Tests for media player service call mocking."""

from pytest import approx

from ha_integration_test_harness import HomeAssistant


class TestPlayMedia:

    def test_play_media_transitions_to_playing(self, home_assistant: HomeAssistant) -> None:
        """Test that play_media transitions state to playing and stores media attributes."""
        home_assistant.given_an_entity("media_player.test_speaker", "idle")

        home_assistant.call_action(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.test_speaker",
                "media_content_id": "http://radio.stream/live",
                "media_content_type": "music",
            },
        )

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={
                "media_content_id": "http://radio.stream/live",
                "media_content_type": "music",
            },
        )

    def test_play_media_auto_powers_on(self, home_assistant: HomeAssistant) -> None:
        """Test that play_media auto-powers-on from off state."""
        home_assistant.given_an_entity("media_player.test_speaker", "off")

        home_assistant.call_action(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.test_speaker",
                "media_content_id": "http://radio.stream/live",
                "media_content_type": "music",
            },
        )

        home_assistant.assert_entity_state("media_player.test_speaker", "playing")


class TestTransportControls:

    def test_media_play_from_paused(self, home_assistant: HomeAssistant) -> None:
        """Test that media_play transitions from paused to playing."""
        home_assistant.given_an_entity("media_player.test_speaker", "paused")

        home_assistant.call_action("media_player", "media_play", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state("media_player.test_speaker", "playing")

    def test_media_pause_from_playing(self, home_assistant: HomeAssistant) -> None:
        """Test that media_pause transitions from playing to paused."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action("media_player", "media_pause", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state("media_player.test_speaker", "paused")

    def test_media_stop_clears_metadata(self, home_assistant: HomeAssistant) -> None:
        """Test that media_stop transitions to idle and clears media metadata."""
        home_assistant.given_an_entity("media_player.test_speaker", "idle")
        home_assistant.call_action(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.test_speaker",
                "media_content_id": "test_url",
                "media_content_type": "music",
            },
        )
        home_assistant.assert_entity_state("media_player.test_speaker", "playing")

        home_assistant.call_action("media_player", "media_stop", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state("media_player.test_speaker", "idle")
        state = home_assistant.get_state("media_player.test_speaker")
        assert state is not None
        assert state["attributes"].get("media_content_id") is None
        assert state["attributes"].get("media_content_type") is None

    def test_media_play_pause_toggles(self, home_assistant: HomeAssistant) -> None:
        """Test that media_play_pause toggles between playing and paused."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action("media_player", "media_play_pause", {"entity_id": "media_player.test_speaker"})
        home_assistant.assert_entity_state("media_player.test_speaker", "paused")

        home_assistant.call_action("media_player", "media_play_pause", {"entity_id": "media_player.test_speaker"})
        home_assistant.assert_entity_state("media_player.test_speaker", "playing")


class TestTrackControls:

    def test_next_track_increments(self, home_assistant: HomeAssistant) -> None:
        """Test that media_next_track increments media_track attribute."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action("media_player", "media_next_track", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"media_track": 1},
        )

    def test_previous_track_decrements(self, home_assistant: HomeAssistant) -> None:
        """Test that media_previous_track decrements media_track."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")
        home_assistant.call_action("media_player", "media_next_track", {"entity_id": "media_player.test_speaker"})
        home_assistant.call_action("media_player", "media_next_track", {"entity_id": "media_player.test_speaker"})

        home_assistant.call_action("media_player", "media_previous_track", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"media_track": 1},
        )

    def test_previous_track_clamped_at_zero(self, home_assistant: HomeAssistant) -> None:
        """Test that media_previous_track stays at 0 when already at 0."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action("media_player", "media_previous_track", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"media_track": 0},
        )

    def test_media_seek_sets_position(self, home_assistant: HomeAssistant) -> None:
        """Test that media_seek sets media_position attribute."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action(
            "media_player",
            "media_seek",
            {"entity_id": "media_player.test_speaker", "seek_position": 120},
        )

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"media_position": 120},
        )


class TestVolumeControls:

    def test_volume_set(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_set updates volume_level."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": 0.5},
        )

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"volume_level": approx(0.5)},
        )

    def test_volume_up(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_up increases volume by 0.1."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")
        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": 0.5},
        )

        home_assistant.call_action("media_player", "volume_up", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"volume_level": approx(0.6)},
        )

    def test_volume_down(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_down decreases volume by 0.1."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")
        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": 0.5},
        )

        home_assistant.call_action("media_player", "volume_down", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"volume_level": approx(0.4)},
        )

    def test_volume_mute(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_mute updates is_volume_muted."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action(
            "media_player",
            "volume_mute",
            {"entity_id": "media_player.test_speaker", "is_volume_muted": True},
        )

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "playing",
            expected_attributes={"is_volume_muted": True},
        )

    def test_volume_works_when_off(self, home_assistant: HomeAssistant) -> None:
        """Test that volume actions work when entity is off."""
        home_assistant.given_an_entity("media_player.test_speaker", "off")

        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": 0.7},
        )

        home_assistant.assert_entity_state(
            "media_player.test_speaker",
            "off",
            expected_attributes={"volume_level": approx(0.7)},
        )


class TestEdgeCases:

    def test_media_play_when_off_is_noop(self, home_assistant: HomeAssistant) -> None:
        """Test that media_play when off doesn't change state."""
        home_assistant.given_an_entity("media_player.test_speaker", "off")

        home_assistant.call_action("media_player", "media_play", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state("media_player.test_speaker", "off")

    def test_media_pause_when_idle_is_noop(self, home_assistant: HomeAssistant) -> None:
        """Test that media_pause when idle doesn't change state."""
        home_assistant.given_an_entity("media_player.test_speaker", "idle")

        home_assistant.call_action("media_player", "media_pause", {"entity_id": "media_player.test_speaker"})

        home_assistant.assert_entity_state("media_player.test_speaker", "idle")

    def test_volume_set_clamped_high(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_set clamps to 1.0."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": 1.5},
        )

        state = home_assistant.get_state("media_player.test_speaker")
        assert state is not None
        assert state["attributes"]["volume_level"] == 1.0

    def test_volume_set_clamped_low(self, home_assistant: HomeAssistant) -> None:
        """Test that volume_set clamps to 0.0."""
        home_assistant.given_an_entity("media_player.test_speaker", "playing")

        home_assistant.call_action(
            "media_player",
            "volume_set",
            {"entity_id": "media_player.test_speaker", "volume_level": -0.5},
        )

        state = home_assistant.get_state("media_player.test_speaker")
        assert state is not None
        assert state["attributes"]["volume_level"] == 0.0
