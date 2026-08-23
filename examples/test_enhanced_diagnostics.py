"""Tests for enhanced container diagnostics (issue #169)."""

import subprocess
from unittest.mock import MagicMock, patch

import requests

from ha_integration_test_harness.docker_manager import DockerComposeManager, DockerContainer


def _make_manager() -> DockerComposeManager:
    manager = DockerComposeManager.__new__(DockerComposeManager)
    manager._run_id = "testrun123"
    manager._containers = {
        "homeassistant": DockerContainer(
            service="homeassistant",
            name="test-ha-1",
            container_id="abc123",
            url="http://localhost:8123",
            local_port=8123,
            mapped_port=8123,
            status="running",
            health="healthy",
            exit_code=0,
            std_out="",
            std_err="",
        ),
        "appdaemon": DockerContainer(
            service="appdaemon",
            name="test-ad-1",
            container_id="def456",
            url="http://localhost:5050",
            local_port=5050,
            mapped_port=5050,
            status="running",
            health="healthy",
            exit_code=0,
            std_out="",
            std_err="",
        ),
    }
    manager._containers_dir = "/fake/containers"
    return manager


class TestCollectDockerNetworkState:

    def test_captures_network_inspect_output(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_result = MagicMock()
        mock_result.stdout = '[{"Name": "testrun123_default", "Containers": {}}]'
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_result) as mock_run:
            manager._collect_docker_network_state(logs)
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[:4] == ["docker", "network", "inspect", "testrun123_default"]
        assert any("DOCKER NETWORK STATE" in line for line in logs)
        assert any("testrun123_default" in line for line in logs)

    def test_handles_command_failure(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="network not found")):
            manager._collect_docker_network_state(logs)
        assert any("ERROR" in line for line in logs)

    def test_handles_unexpected_exception(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", side_effect=OSError("docker not found")):
            manager._collect_docker_network_state(logs)
        assert any("ERROR" in line for line in logs)


class TestCollectTcpConnectionState:

    def test_captures_tcp_state(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_result = MagicMock()
        mock_result.stdout = "tcp 0 0 0.0.0.0:8123 0.0.0.0:* LISTEN"
        mock_result.stderr = ""
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_result) as mock_run:
            manager._collect_tcp_connection_state(logs)
            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "exec" in call_args
            assert "test-ha-1" in call_args
        assert any("TCP CONNECTION STATE" in line for line in logs)
        assert any("8123" in line for line in logs)

    def test_handles_missing_ha_container(self) -> None:
        manager = _make_manager()
        manager._containers = {}
        logs: list[str] = []
        manager._collect_tcp_connection_state(logs)
        assert any("ERROR" in line for line in logs)

    def test_handles_command_failure_gracefully(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", side_effect=Exception("exec failed")):
            manager._collect_tcp_connection_state(logs)
        assert any("ERROR" in line for line in logs)


class TestCollectMultiEndpointApiProbing:

    def test_probes_all_endpoints(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("ha_integration_test_harness.docker_manager.requests.get", return_value=mock_response):
            manager._collect_multi_endpoint_api_probing(logs)
        assert any("API ENDPOINT TESTS" in line for line in logs)
        assert any("/api/" in line for line in logs)
        assert any("/api/states" in line for line in logs)
        endpoint_lines = [line for line in logs if line.startswith("/")]
        assert len(endpoint_lines) == 3

    def test_reports_timeout(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.requests.get", side_effect=requests.Timeout()):
            manager._collect_multi_endpoint_api_probing(logs)
        assert any("TIMEOUT" in line for line in logs)

    def test_reports_connection_refused(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.requests.get", side_effect=requests.ConnectionError()):
            manager._collect_multi_endpoint_api_probing(logs)
        assert any("CONNECTION REFUSED" in line for line in logs)

    def test_handles_missing_ha_container(self) -> None:
        manager = _make_manager()
        manager._containers = {}
        logs: list[str] = []
        manager._collect_multi_endpoint_api_probing(logs)
        assert any("ERROR" in line for line in logs)

    def test_reports_response_times(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("ha_integration_test_harness.docker_manager.requests.get", return_value=mock_response):
            manager._collect_multi_endpoint_api_probing(logs)
        endpoint_lines = [line for line in logs if line.startswith("/")]
        for line in endpoint_lines:
            assert "s)" in line


class TestCollectHealthCheckCorrelation:

    def test_reports_healthy_and_reachable(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_inspect = MagicMock()
        mock_inspect.stdout = "healthy\n"
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_inspect):
            with patch("ha_integration_test_harness.docker_manager.requests.get", return_value=mock_response):
                manager._collect_health_check_correlation(logs)
        assert any("HEALTH CHECK VS API" in line for line in logs)
        assert any("Docker Health: healthy" in line for line in logs)
        assert any("API Reachable: yes" in line for line in logs)
        assert any("Correlation:" in line and "agree" in line for line in logs)

    def test_detects_health_api_mismatch(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_inspect = MagicMock()
        mock_inspect.stdout = "healthy\n"
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_inspect):
            with patch("ha_integration_test_harness.docker_manager.requests.get", side_effect=requests.Timeout()):
                manager._collect_health_check_correlation(logs)
        assert any("Docker Health: healthy" in line for line in logs)
        assert any("API Reachable: no" in line for line in logs)
        assert any("WARNING" in line and "healthy but API is unreachable" in line for line in logs)

    def test_handles_missing_ha_container(self) -> None:
        manager = _make_manager()
        manager._containers = {}
        logs: list[str] = []
        manager._collect_health_check_correlation(logs)
        assert any("ERROR" in line for line in logs)

    def test_handles_inspect_failure(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", side_effect=subprocess.CalledProcessError(1, "docker", stderr="no such container")):
            manager._collect_health_check_correlation(logs)
        assert any("ERROR" in line for line in logs)


class TestCollectExtendedHaLogs:

    def test_captures_extended_logs(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_result = MagicMock()
        mock_result.stdout = "line1\nline2\nline3\n" * 100
        mock_result.stderr = ""
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_result) as mock_run:
            manager._collect_extended_ha_logs(logs)
            assert mock_run.call_count == 2
            first_call_args = mock_run.call_args_list[0][0][0]
            second_call_args = mock_run.call_args_list[1][0][0]
            assert "--tail=500" in first_call_args
            assert "--since=2m" in second_call_args
            assert "abc123" in first_call_args
            assert "abc123" in second_call_args
        assert any("EXTENDED HA LOGS" in line for line in logs)

    def test_handles_empty_logs(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_result):
            manager._collect_extended_ha_logs(logs)
        assert any("<<empty>>" in line for line in logs)

    def test_handles_missing_ha_container(self) -> None:
        manager = _make_manager()
        manager._containers = {}
        logs: list[str] = []
        manager._collect_extended_ha_logs(logs)
        assert any("ERROR" in line for line in logs)


class TestCollectProcessState:

    def test_captures_process_list(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        mock_result = MagicMock()
        mock_result.stdout = "PID   USER   COMMAND\n1     root   python3 -m homeassistant"
        mock_result.stderr = ""
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_result) as mock_run:
            manager._collect_process_state(logs)
            call_args = mock_run.call_args[0][0]
            assert "docker" in call_args
            assert "exec" in call_args
            assert "test-ha-1" in call_args
        assert any("HA PROCESS STATE" in line for line in logs)
        assert any("homeassistant" in line for line in logs)

    def test_handles_missing_ha_container(self) -> None:
        manager = _make_manager()
        manager._containers = {}
        logs: list[str] = []
        manager._collect_process_state(logs)
        assert any("ERROR" in line for line in logs)

    def test_handles_command_failure_gracefully(self) -> None:
        manager = _make_manager()
        logs: list[str] = []
        with patch("ha_integration_test_harness.docker_manager.subprocess.run", side_effect=Exception("exec failed")):
            manager._collect_process_state(logs)
        assert any("ERROR" in line for line in logs)


class TestGetContainerDiagnosticsIntegration:

    def test_calls_all_enhanced_collectors(self) -> None:
        manager = _make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_subprocess_result = MagicMock()
        mock_subprocess_result.stdout = "mock output"
        mock_subprocess_result.stderr = ""

        with patch.object(manager, "_refresh_container_details", return_value=manager._containers):
            with patch("ha_integration_test_harness.docker_manager.subprocess.run", return_value=mock_subprocess_result):
                with patch("ha_integration_test_harness.docker_manager.requests.get", return_value=mock_response):
                    result = manager.get_container_diagnostics(test_name="test_foo", test_duration=10.5)
        assert "CONTAINER DIAGNOSTICS" in result
        assert "DOCKER NETWORK STATE" in result
        assert "TCP CONNECTION STATE" in result
        assert "API ENDPOINT TESTS" in result
        assert "HEALTH CHECK VS API" in result
        assert "EXTENDED HA LOGS" in result
        assert "HA PROCESS STATE" in result
        assert "END DIAGNOSTICS" in result
        assert "test_foo" in result
        assert "10.50s" in result
