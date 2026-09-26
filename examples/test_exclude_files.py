"""Tests for file exclusion during configuration deployment.

This module tests the ability to exclude specific files from being copied
during the configuration deployment process, via pytest ini option or constructor parameter.
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure worktree src is loaded first (before importing the module under test)
worktree_src = str(Path(__file__).parent.parent / "src")
if worktree_src not in sys.path:
    sys.path.insert(0, worktree_src)

from ha_integration_test_harness.docker_manager import DockerComposeManager  # noqa: E402


class TestExcludeFilesConstructor:
    """Tests for DockerComposeManager exclude_files parameter."""

    def test_init_accepts_exclude_files_parameter(self) -> None:
        """Test that DockerComposeManager accepts exclude_files parameter."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=MagicMock()),
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()),
        ):
            manager = DockerComposeManager(exclude_files=["automations/test.yaml"])
            assert manager._exclude_files == ["automations/test.yaml"]

    def test_init_defaults_to_empty_list_when_not_provided(self) -> None:
        """Test that DockerComposeManager defaults exclude_files to empty list."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=MagicMock()),
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()),
        ):
            manager = DockerComposeManager()
            assert manager._exclude_files == []

    def test_init_accepts_none_as_exclude_files(self) -> None:
        """Test that DockerComposeManager accepts None for exclude_files."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=MagicMock()),
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()),
        ):
            manager = DockerComposeManager(exclude_files=None)
            assert manager._exclude_files == []


class TestExcludeFilesDeployment:
    """Tests for file exclusion during configuration deployment."""

    def _create_ha_config(self, temp_dir: str) -> Path:
        """Create a minimal Home Assistant configuration directory structure."""
        ha_root = Path(temp_dir) / "ha_config"
        ha_root.mkdir()
        (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")
        return ha_root

    def _create_manager(self, ha_root: Path, exclude_files: list[str]) -> DockerComposeManager:
        """Create a DockerComposeManager with mocked detection methods."""
        with (
            patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root),
            patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()),
        ):
            return DockerComposeManager(exclude_files=exclude_files)

    def test_deployment_excludes_exact_file_path(self) -> None:
        """Test that deployment excludes a file when exact path is provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = self._create_ha_config(temp_dir)
            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test_automation.yaml").write_text("automation: test")
            (automations_dir / "keep_automation.yaml").write_text("automation: keep")

            manager = self._create_manager(ha_root, ["automations/test_automation.yaml"])
            staged_path = manager._stage_ha_config_with_entities()

            try:
                # Excluded file should not exist
                assert not (staged_path / "automations" / "test_automation.yaml").exists()
                # Non-excluded file should exist
                assert (staged_path / "automations" / "keep_automation.yaml").exists()
                # configuration.yaml should always be present
                assert (staged_path / "configuration.yaml").exists()
            finally:
                shutil.rmtree(staged_path, ignore_errors=True)

    def test_deployment_excludes_glob_pattern(self) -> None:
        """Test that deployment excludes files matching a glob pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = self._create_ha_config(temp_dir)
            automations_dir = ha_root / "automations" / "maintenance"
            automations_dir.mkdir(parents=True)
            (automations_dir / "monitor1.yaml").write_text("automation: monitor1")
            (automations_dir / "monitor2.yaml").write_text("automation: monitor2")
            (automations_dir / "other.txt").write_text("not yaml")

            manager = self._create_manager(ha_root, ["automations/maintenance/*.yaml"])
            staged_path = manager._stage_ha_config_with_entities()

            try:
                # Glob-matched files should not exist
                assert not (staged_path / "automations" / "maintenance" / "monitor1.yaml").exists()
                assert not (staged_path / "automations" / "maintenance" / "monitor2.yaml").exists()
                # Non-matched file (different extension) should exist
                assert (staged_path / "automations" / "maintenance" / "other.txt").exists()
            finally:
                shutil.rmtree(staged_path, ignore_errors=True)

    def test_deployment_silently_ignores_non_matching_pattern(self) -> None:
        """Test that deployment succeeds when exclusion pattern doesn't match any files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = self._create_ha_config(temp_dir)
            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test.yaml").write_text("automation: test")

            manager = self._create_manager(ha_root, ["nonexistent/path.yaml"])
            staged_path = manager._stage_ha_config_with_entities()

            try:
                # Deployment should succeed, existing files should be present
                assert (staged_path / "automations" / "test.yaml").exists()
            finally:
                shutil.rmtree(staged_path, ignore_errors=True)

    def test_deployment_handles_empty_exclude_list(self) -> None:
        """Test that deployment works normally with empty exclude list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = self._create_ha_config(temp_dir)
            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test.yaml").write_text("automation: test")

            manager = self._create_manager(ha_root, [])
            staged_path = manager._stage_ha_config_with_entities()

            try:
                # All files should be present
                assert (staged_path / "automations" / "test.yaml").exists()
            finally:
                shutil.rmtree(staged_path, ignore_errors=True)

    def test_deployment_excludes_multiple_patterns(self) -> None:
        """Test that deployment excludes files matching any of multiple patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = self._create_ha_config(temp_dir)
            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "exclude1.yaml").write_text("automation: exclude1")
            (automations_dir / "exclude2.yaml").write_text("automation: exclude2")
            (automations_dir / "keep.yaml").write_text("automation: keep")

            manager = self._create_manager(
                ha_root,
                ["automations/exclude1.yaml", "automations/exclude2.yaml"],
            )
            staged_path = manager._stage_ha_config_with_entities()

            try:
                # Excluded files should not exist
                assert not (staged_path / "automations" / "exclude1.yaml").exists()
                assert not (staged_path / "automations" / "exclude2.yaml").exists()
                # Non-excluded file should exist
                assert (staged_path / "automations" / "keep.yaml").exists()
            finally:
                shutil.rmtree(staged_path, ignore_errors=True)
