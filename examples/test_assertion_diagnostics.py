"""Tests for failed assertion diagnostics (issue #120)."""

from datetime import datetime

import pytest

from ha_integration_test_harness import HomeAssistant


class TestFormatStateHistory:

    def _make_client(self) -> HomeAssistant:
        return HomeAssistant("http://localhost:8123", "test-token")

    def test_no_history_returns_no_changes_message(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        result = client._format_state_history([], test_start)
        assert result == "No state changes recorded during this test."

    def test_none_history_returns_unavailable_message(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        result = client._format_state_history(None, test_start)
        assert result == "State change history unavailable."

    def test_single_state_change(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = [
            {
                "entity_id": "sensor.temp",
                "state": "25.0",
                "attributes": {"unit_of_measurement": "\u00b0C"},
                "last_changed": "2026-08-22T14:20:02.300000+00:00",
                "last_updated": "2026-08-22T14:20:02.300000+00:00",
            }
        ]
        result = client._format_state_history(history, test_start)
        assert "State change history:" in result
        assert "25.0" in result
        assert "+2.3s" in result
        assert "14:20:02" in result

    def test_attribute_deltas_shown(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = [
            {
                "entity_id": "light.living_room",
                "state": "on",
                "attributes": {"brightness": 100, "color": "red"},
                "last_changed": "2026-08-22T14:20:01+00:00",
                "last_updated": "2026-08-22T14:20:01+00:00",
            },
            {
                "entity_id": "light.living_room",
                "state": "on",
                "attributes": {"brightness": 200, "color": "blue"},
                "last_changed": "2026-08-22T14:20:03+00:00",
                "last_updated": "2026-08-22T14:20:03+00:00",
            },
        ]
        result = client._format_state_history(history, test_start)
        assert "brightness" in result
        assert "color" in result

    def test_new_attribute_marked(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = [
            {
                "entity_id": "sensor.temp",
                "state": "on",
                "attributes": {},
                "last_changed": "2026-08-22T14:20:01+00:00",
                "last_updated": "2026-08-22T14:20:01+00:00",
            },
            {
                "entity_id": "sensor.temp",
                "state": "on",
                "attributes": {"brightness": 50},
                "last_changed": "2026-08-22T14:20:02+00:00",
                "last_updated": "2026-08-22T14:20:02+00:00",
            },
        ]
        result = client._format_state_history(history, test_start)
        assert "(new)" in result

    def test_removed_attribute_marked(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = [
            {
                "entity_id": "sensor.temp",
                "state": "on",
                "attributes": {"brightness": 50},
                "last_changed": "2026-08-22T14:20:01+00:00",
                "last_updated": "2026-08-22T14:20:01+00:00",
            },
            {
                "entity_id": "sensor.temp",
                "state": "on",
                "attributes": {},
                "last_changed": "2026-08-22T14:20:02+00:00",
                "last_updated": "2026-08-22T14:20:02+00:00",
            },
        ]
        result = client._format_state_history(history, test_start)
        assert "(removed)" in result

    def test_truncation_shows_omitted_count(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = []
        for i in range(15):
            history.append(
                {
                    "entity_id": "sensor.temp",
                    "state": str(i),
                    "attributes": {},
                    "last_changed": f"2026-08-22T14:20:{i:02d}+00:00",
                    "last_updated": f"2026-08-22T14:20:{i:02d}+00:00",
                }
            )
        result = client._format_state_history(history, test_start)
        assert "5 more changes" in result

    def test_unregistered_marker(self) -> None:
        client = self._make_client()
        test_start = datetime(2026, 8, 22, 14, 20, 0)
        history = [
            {
                "entity_id": "sensor.temp",
                "state": "on",
                "attributes": {},
                "last_changed": "2026-08-22T14:20:01+00:00",
                "last_updated": "2026-08-22T14:20:01+00:00",
            },
            {
                "entity_id": "sensor.temp",
                "state": "unavailable",
                "attributes": {},
                "last_changed": "2026-08-22T14:20:02+00:00",
                "last_updated": "2026-08-22T14:20:02+00:00",
            },
        ]
        result = client._format_state_history(history, test_start)
        assert "[unregistered]" in result


class TestAssertionDiagnosticsIntegration:

    def test_diagnostics_appear_on_timeout(self, home_assistant: HomeAssistant) -> None:
        home_assistant.given_an_entity("sensor.diag_test", state="initial")
        with pytest.raises(AssertionError, match="did not reach expected conditions") as exc_info:
            home_assistant.assert_entity_state("sensor.diag_test", "expected_state", timeout=2)
        error_msg = str(exc_info.value)
        assert "State change history:" in error_msg or "No state changes recorded" in error_msg

    def test_no_diagnostics_for_entity_not_found(self, home_assistant: HomeAssistant) -> None:
        with pytest.raises(AssertionError, match="not found"):
            home_assistant.assert_entity_state("sensor.nonexistent_entity_xyz", "on", timeout=2)
