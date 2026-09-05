"""Tests for Home Assistant image override feature.

This module tests the ability to override the Home Assistant Docker image
via environment variable, pytest configuration, or fixture.
"""

from unittest.mock import MagicMock, patch

import pytest

from ha_integration_test_harness.docker_manager import DockerComposeManager


class TestDockerComposeManagerHAImage:
    """Tests for DockerComposeManager ha_image parameter."""

    def test_init_accepts_ha_image_parameter(self) -> None:
        """Test that DockerComposeManager accepts ha_image parameter."""
        with patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha, patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad:
            mock_detect_ha.return_value = MagicMock()
            mock_detect_ad.return_value = MagicMock()

            manager = DockerComposeManager(ha_image="homeassistant/home-assistant:2026.7")

            assert manager._ha_image == "homeassistant/home-assistant:2026.7"

    def test_init_defaults_to_none_when_ha_image_not_provided(self) -> None:
        """Test that DockerComposeManager defaults ha_image to None when not provided."""
        with patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha, patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad:
            mock_detect_ha.return_value = MagicMock()
            mock_detect_ad.return_value = MagicMock()

            manager = DockerComposeManager()

            assert manager._ha_image is None

    def test_start_passes_ha_image_env_var_to_docker_compose(self) -> None:
        """Test that start() passes HA_IMAGE environment variable to docker-compose."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha,
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad,
            patch.object(DockerComposeManager, "_stage_ha_config_with_entities") as mock_stage,
            patch("subprocess.run") as mock_run,
            patch.object(DockerComposeManager, "_refresh_container_details") as mock_refresh,
        ):
            mock_ha_root = MagicMock()
            mock_ha_root.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
            mock_detect_ha.return_value = mock_ha_root
            mock_detect_ad.return_value = MagicMock()
            mock_stage.return_value = MagicMock()
            mock_refresh.return_value = {}

            manager = DockerComposeManager(ha_image="homeassistant/home-assistant:2026.7")
            manager.start()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs["env"]
            assert env["HA_IMAGE"] == "homeassistant/home-assistant:2026.7"

    def test_start_does_not_pass_ha_image_when_none(self) -> None:
        """Test that start() does not pass HA_IMAGE when ha_image is None."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha,
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad,
            patch.object(DockerComposeManager, "_stage_ha_config_with_entities") as mock_stage,
            patch("subprocess.run") as mock_run,
            patch.object(DockerComposeManager, "_refresh_container_details") as mock_refresh,
        ):
            mock_ha_root = MagicMock()
            mock_ha_root.__truediv__ = MagicMock(return_value=MagicMock(exists=MagicMock(return_value=True)))
            mock_detect_ha.return_value = mock_ha_root
            mock_detect_ad.return_value = MagicMock()
            mock_stage.return_value = MagicMock()
            mock_refresh.return_value = {}

            manager = DockerComposeManager()
            manager.start()

            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs["env"]
            assert "HA_IMAGE" not in env


class TestHAImageConfiguration:
    """Tests for ha_image pytest configuration."""

    def test_pytest_config_reads_ha_image(self, pytestconfig: pytest.Config) -> None:
        """Test that pytest config can read ha_image option."""
        ha_image = pytestconfig.getini("ha_image")
        assert ha_image is None or isinstance(ha_image, str)
