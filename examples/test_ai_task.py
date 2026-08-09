"""Tests for ai_task service mocking."""

import uuid

from ha_integration_test_harness import HomeAssistant


class TestGenerateData:

    def test_generate_data_returns_mock_response(self, home_assistant: HomeAssistant) -> None:
        """Test that ai_task.generate_data returns a fixed mock response."""
        response = home_assistant.call_action_with_response(
            "ai_task",
            "generate_data",
            {
                "task_name": "Test task",
                "instructions": "Generate test data",
            },
        )

        assert "conversation_id" in response
        assert "data" in response
        assert response["data"] == "Mock AI response"
        assert uuid.UUID(response["conversation_id"])


class TestAutomationWithResponseVariable:

    def test_automation_uses_ai_task_response(self, home_assistant: HomeAssistant) -> None:
        """Test that an automation can use ai_task.generate_data response_variable."""
        home_assistant.call_action(
            "input_button",
            "press",
            {"entity_id": "input_button.ai_task_trigger"},
        )

        home_assistant.assert_entity_state(
            "input_text.ai_greeting_result",
            "Mock AI response",
        )
