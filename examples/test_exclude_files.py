"""Tests for file exclusion during HA config staging.

This module tests the ability to exclude specific files from being copied
during the config staging process, via pytest ini option or constructor parameter.
"""

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
        with patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha, patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad:
            mock_detect_ha.return_value = MagicMock()
            mock_detect_ad.return_value = MagicMock()

            manager = DockerComposeManager(exclude_files=["automations/test.yaml"])

            assert manager._exclude_files == ["automations/test.yaml"]

    def test_init_defaults_to_empty_list_when_not_provided(self) -> None:
        """Test that DockerComposeManager defaults exclude_files to empty list."""
        with patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha, patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad:
            mock_detect_ha.return_value = MagicMock()
            mock_detect_ad.return_value = MagicMock()

            manager = DockerComposeManager()

            assert manager._exclude_files == []

    def test_init_accepts_none_as_exclude_files(self) -> None:
        """Test that DockerComposeManager accepts None for exclude_files."""
        with patch.object(DockerComposeManager, "_detect_ha_config_root") as mock_detect_ha, patch.object(DockerComposeManager, "_detect_appdaemon_config_root") as mock_detect_ad:
            mock_detect_ha.return_value = MagicMock()
            mock_detect_ad.return_value = MagicMock()

            manager = DockerComposeManager(exclude_files=None)

            assert manager._exclude_files == []


class TestExcludeFilesStaging:
    """Tests for file exclusion during staging."""

    def test_staging_excludes_exact_file_path(self) -> None:
        """Test that staging excludes a file when exact path is provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = Path(temp_dir) / "ha_config"
            ha_root.mkdir()
            (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")

            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test_automation.yaml").write_text("automation: test")
            (automations_dir / "keep_automation.yaml").write_text("automation: keep")

            with patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root), patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()):

                manager = DockerComposeManager(exclude_files=["automations/test_automation.yaml"])
                staged_path = manager._stage_ha_config_with_entities()

                try:
                    # Excluded file should not exist
                    assert not (staged_path / "automations" / "test_automation.yaml").exists()
                    # Non-excluded file should exist
                    assert (staged_path / "automations" / "keep_automation.yaml").exists()
                    # configuration.yaml should always be present
                    assert (staged_path / "configuration.yaml").exists()
                finally:
                    import shutil

                    shutil.rmtree(staged_path, ignore_errors=True)

    def test_staging_excludes_glob_pattern(self) -> None:
        """Test that staging excludes files matching a glob pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = Path(temp_dir) / "ha_config"
            ha_root.mkdir()
            (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")

            automations_dir = ha_root / "automations" / "maintenance"
            automations_dir.mkdir(parents=True)
            (automations_dir / "monitor1.yaml").write_text("automation: monitor1")
            (automations_dir / "monitor2.yaml").write_text("automation: monitor2")
            (automations_dir / "other.txt").write_text("not yaml")

            with patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root), patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()):

                manager = DockerComposeManager(exclude_files=["automations/maintenance/*.yaml"])
                staged_path = manager._stage_ha_config_with_entities()

                try:
                    # Glob-matched files should not exist
                    assert not (staged_path / "automations" / "maintenance" / "monitor1.yaml").exists()
                    assert not (staged_path / "automations" / "maintenance" / "monitor2.yaml").exists()
                    # Non-matched file (different extension) should exist
                    assert (staged_path / "automations" / "maintenance" / "other.txt").exists()
                finally:
                    import shutil

                    shutil.rmtree(staged_path, ignore_errors=True)

    def test_staging_silently_ignores_non_matching_pattern(self) -> None:
        """Test that staging succeeds when exclusion pattern doesn't match any files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = Path(temp_dir) / "ha_config"
            ha_root.mkdir()
            (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")

            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test.yaml").write_text("automation: test")

            with patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root), patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()):

                # Pattern doesn't match any existing files
                manager = DockerComposeManager(exclude_files=["nonexistent/path.yaml"])
                staged_path = manager._stage_ha_config_with_entities()

                try:
                    # Staging should succeed, existing files should be present
                    assert (staged_path / "automations" / "test.yaml").exists()
                finally:
                    import shutil

                    shutil.rmtree(staged_path, ignore_errors=True)

    def test_staging_handles_empty_exclude_list(self) -> None:
        """Test that staging works normally with empty exclude list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = Path(temp_dir) / "ha_config"
            ha_root.mkdir()
            (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")

            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "test.yaml").write_text("automation: test")

            with patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root), patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()):

                manager = DockerComposeManager(exclude_files=[])
                staged_path = manager._stage_ha_config_with_entities()

                try:
                    # All files should be present
                    assert (staged_path / "automations" / "test.yaml").exists()
                finally:
                    import shutil

                    shutil.rmtree(staged_path, ignore_errors=True)

    def test_staging_excludes_multiple_patterns(self) -> None:
        """Test that staging excludes files matching any of multiple patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            ha_root = Path(temp_dir) / "ha_config"
            ha_root.mkdir()
            (ha_root / "configuration.yaml").write_text("homeassistant:\n  name: My Home\n")

            automations_dir = ha_root / "automations"
            automations_dir.mkdir()
            (automations_dir / "exclude1.yaml").write_text("automation: exclude1")
            (automations_dir / "exclude2.yaml").write_text("automation: exclude2")
            (automations_dir / "keep.yaml").write_text("automation: keep")

            with patch.object(DockerComposeManager, "_detect_ha_config_root", return_value=ha_root), patch.object(DockerComposeManager, "_detect_appdaemon_config_root", return_value=MagicMock()):

                manager = DockerComposeManager(exclude_files=["automations/exclude1.yaml", "automations/exclude2.yaml"])
                staged_path = manager._stage_ha_config_with_entities()

                try:
                    # Excluded files should not exist
                    assert not (staged_path / "automations" / "exclude1.yaml").exists()
                    assert not (staged_path / "automations" / "exclude2.yaml").exists()
                    # Non-excluded file should exist
                    assert (staged_path / "automations" / "keep.yaml").exists()
                finally:
                    import shutil

                    shutil.rmtree(staged_path, ignore_errors=True)
