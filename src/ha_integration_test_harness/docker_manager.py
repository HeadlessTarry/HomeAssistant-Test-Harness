"""Docker Compose manager for integration test environment."""

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
import yaml

from .exceptions import DockerError, PersistentEntityError

logger = logging.getLogger(__name__)


class DockerContainer:
    """Represents a Docker container in the test environment."""

    def __init__(
        self, service: str, name: str, container_id: str, url: str, local_port: int | None, mapped_port: int | None, status: str, health: str | None, exit_code: int | None, std_out: str, std_err: str
    ) -> None:
        """Initialize the Docker container representation.

        Args:
            service: The docker-compose service name associated with this container.
            name: The name of the container.
            container_id: The Docker container ID.
            url: The HTTP base URL for accessing the service running in the container.
            local_port: The local (host) port used to access the container, or ``None`` if not applicable.
            mapped_port: The container's internal port that is mapped to ``local_port``, or ``None`` if not applicable.
            status: The current container status (for example, ``"running"`` or ``"exited"``).
            health: The health status reported by Docker, or ``None`` if no health check is defined.
            exit_code: The container's exit code if it has stopped, or ``None`` if it is still running or not yet exited.
            std_out: The captured standard output from the container.
            std_err: The captured standard error output from the container.
        """
        self.service = service
        self.name = name
        self.container_id = container_id
        self.url = url
        self.local_port = local_port
        self.mapped_port = mapped_port
        self.status = status
        self.health = health
        self.exit_code = exit_code
        self.std_out = std_out
        self.std_err = std_err

    def __str__(self) -> str:
        """String representation of the Docker container."""
        info = [
            f"Service: {self.service}",
            f"Container: {self.name} (ID: {self.container_id})",
            f"URL: {self.url}",
            f"Local Port: {self.local_port}",
            f"Mapped Port: {self.mapped_port}",
            f"Status: {self.status}",
            f"Health: {self.health}",
            f"Exit Code: {self.exit_code}",
            f"Std Out:\n{self.std_out}",
            f"Std Err:\n{self.std_err}",
        ]
        return "\n".join(info)


class DockerComposeManager:
    """Manages Docker Compose test environment lifecycle.

    This class handles all Docker operations for the integration test environment,
    including starting/stopping containers, port discovery, and file I/O operations
    with running containers.

    The environment includes:
    - Home Assistant on localhost:<dynamic-port>
    - AppDaemon on localhost:<dynamic-port>

    Docker assigns ephemeral ports automatically to enable parallel test runs.
    """

    def __init__(self, persistent_entities_path: Optional[str] = None) -> None:
        """Initialize the Docker Compose manager.

        Sets up paths and generates a unique run ID for container isolation.
        The environment is not started automatically; call start() to launch it.

        Args:
            persistent_entities_path: Optional path to a YAML file containing persistent
                Home Assistant entity definitions to be registered during container startup.

        Raises:
            DockerError: If configuration.yaml is not found in the detected Home Assistant root directory.
            PersistentEntityError: If persistent entities file is invalid or cannot be processed.
        """
        self._run_id = uuid.uuid4().hex

        # Detect Home Assistant configuration root
        self._ha_config_root = self._detect_ha_config_root()

        # Validate that configuration.yaml exists in the Home Assistant root
        config_file = self._ha_config_root / "configuration.yaml"
        if not config_file.exists():
            raise DockerError(
                f"configuration.yaml not found at {config_file}. "
                "Tests must be run from a directory containing a 'home_assistant' subdirectory with your Home Assistant configuration, "
                "or set HOME_ASSISTANT_CONFIG_ROOT environment variable to specify the location. "
                "See: https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/blob/main/documentation/usage.md"
            )

        # Detect AppDaemon configuration root
        self._appdaemon_config_root = self._detect_appdaemon_config_root()

        # Validate that apps.yaml exists in the AppDaemon root (warning only)
        apps_yaml = self._appdaemon_config_root / "apps" / "apps.yaml"
        if not apps_yaml.exists():
            logger.warning(
                f"apps/apps.yaml not found at {apps_yaml}. "
                "AppDaemon may not function correctly. "
                "Ensure you have an 'appdaemon' subdirectory with your AppDaemon configuration, "
                "or set APPDAEMON_CONFIG_ROOT environment variable to specify the location."
            )

        # Set up containers directory path
        self._containers_dir = Path(__file__).parent / "containers"

        if not self._containers_dir.exists():
            raise DockerError(f"Containers directory not found: {self._containers_dir}")

        compose_file = self._containers_dir / "docker-compose.yaml"
        if not compose_file.exists():
            raise DockerError(f"docker-compose.yaml not found: {compose_file}")

        # Container lifecycle state
        self._containers: dict[str, DockerContainer] = {}

        # Persistent entities configuration
        self._persistent_entities_path: Optional[Path] = None
        self._staged_ha_config_root: Optional[Path] = None

        # Load and validate persistent entities if provided
        if persistent_entities_path:
            self._persistent_entities_path = self._validate_persistent_entities_file(persistent_entities_path)

    def _validate_persistent_entities_file(self, path: str) -> Path:
        """Validate that persistent entities file exists and is readable.

        Args:
            path: Path to YAML file containing entity definitions.

        Returns:
            Absolute path to the entities file.

        Raises:
            PersistentEntityError: If file cannot be found or is not readable.
        """
        entity_file = Path(path)
        if not entity_file.exists():
            raise PersistentEntityError(f"Persistent entities file not found: {entity_file.absolute()}")

        if not entity_file.is_file():
            raise PersistentEntityError(f"Persistent entities path is not a file: {entity_file.absolute()}")

        # Try to read and validate it's valid YAML with a suitable top-level structure
        try:
            with open(entity_file, "r") as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise PersistentEntityError(f"Cannot read persistent entities file {entity_file}: {e}")
        except yaml.YAMLError as e:
            raise PersistentEntityError(f"Invalid YAML in persistent entities file {entity_file}: {e}")

        # Home Assistant expects persistent entities packages to be defined as a non-empty mapping
        # at the top level. Empty files, lists, scalars, or other structures will cause startup
        # failures later, so fail fast with a clear error.
        if not isinstance(data, dict) or not data:
            raise PersistentEntityError(
                f"Persistent entities file {entity_file.absolute()} must contain a non-empty YAML mapping suitable for use as homeassistant.packages.<name> (got empty or non-mapping content)."
            )
        logger.info(f"Loaded persistent entities file: {entity_file.absolute()}")
        return entity_file.absolute()

    def _stage_ha_config_with_entities(self) -> Path:
        """Stage Home Assistant config directory with bundled integration and optional entities overlay.

        Creates a temporary copy of the HA config directory, injects the bundled
        ha_test_harness custom integration, and appends the ha_test_harness key to
        configuration.yaml. If persistent entities are configured, also copies the
        entities YAML file and patches configuration.yaml to reference it via
        `homeassistant.packages.test_harness`.

        Returns:
            Path to the staged configuration directory.

        Raises:
            PersistentEntityError: If staging fails.
        """
        # Create temporary staging directory
        staging_dir = Path(tempfile.mkdtemp(prefix="ha_test_config_"))
        logger.debug(f"Staging HA config to: {staging_dir}")

        success = False
        try:
            # Copy original config to staging
            for item in self._ha_config_root.iterdir():
                if item.name in (".storage", "__pycache__"):
                    continue
                src = self._ha_config_root / item.name
                dst = staging_dir / item.name
                if src.is_dir():
                    shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns("__pycache__", ".storage"))
                else:
                    shutil.copy2(src, dst)

            # Inject the bundled ha_test_harness custom integration
            self._inject_custom_integration(staging_dir)

            # Append ha_test_harness: top-level key to configuration.yaml (idempotent)
            self._inject_ha_test_harness_config(staging_dir)

            if self._persistent_entities_path:
                # Copy persistent entities YAML file into staged config root with a unique name
                # to avoid collisions with any existing files in the HA config directory.
                entities_filename = f"_harness_persistent_entities_{uuid.uuid4().hex}.yaml"
                staged_entities_file = staging_dir / entities_filename
                shutil.copy2(self._persistent_entities_path, staged_entities_file)
                logger.debug(f"Copied persistent entities file to: {staged_entities_file}")

                # Patch configuration.yaml to include the entities file
                self._patch_configuration_yaml(staging_dir, entities_filename)

            self._staged_ha_config_root = staging_dir
            success = True
            return staging_dir

        except PersistentEntityError:
            raise
        except (OSError, shutil.Error) as e:
            raise PersistentEntityError(f"Failed to stage Home Assistant configuration: {e}")
        finally:
            if not success and staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _patch_configuration_yaml(self, staged_config_root: Path, entities_filename: str) -> None:
        """Patch configuration.yaml to include persistent entities.

        Ensures configuration.yaml includes:

        homeassistant:
            packages:
                test_harness: !include <persistent entities file>

        Existing `homeassistant` and `homeassistant.packages` keys are preserved.
        The `test_harness` package entry is appended when missing.

        If `homeassistant:` delegates to an included file via `homeassistant: !include <file>`,
        that file is patched instead.

        Args:
            staged_config_root: Root directory of staged config.
            entities_filename: Name of the entities YAML file to include.

        Raises:
            PersistentEntityError: If patching fails.
        """
        config_file = staged_config_root / "configuration.yaml"

        try:
            with open(config_file, "r") as f:
                content = f.read()

            # Quick check: if the entry is already present, skip parsing.
            if f"test_harness: !include {entities_filename}" in content:
                logger.debug("configuration.yaml already includes homeassistant.packages.test_harness")
                return

            # Parse via YAML to locate keys by line number, correctly handling
            # inline comments (e.g. "homeassistant: # comment") and HA-specific
            # tags such as !include, !secret, and !env_var.
            try:
                root_node = yaml.compose(content, Loader=yaml.SafeLoader)
            except yaml.YAMLError as e:
                raise PersistentEntityError(f"Failed to parse configuration.yaml: {e}")

            lines = content.splitlines()

            # Find the top-level homeassistant key node.
            ha_key_node: Optional[yaml.ScalarNode] = None
            ha_val_node: Optional[yaml.Node] = None
            if isinstance(root_node, yaml.MappingNode):
                for key_node, val_node in root_node.value:
                    if isinstance(key_node, yaml.ScalarNode) and key_node.value == "homeassistant":
                        ha_key_node = key_node
                        ha_val_node = val_node
                        break

            if ha_key_node is not None:
                if isinstance(ha_val_node, yaml.MappingNode):
                    if ha_val_node.flow_style:
                        raise PersistentEntityError(
                            "Cannot append persistent entities: 'homeassistant' is a flow-style mapping in configuration.yaml. "
                            "Please convert it to a block mapping before using ha_persistent_entities_path."
                        )
                    # Inline block mapping — patch packages within this content.
                    new_content = self._patch_packages_in_mapping(content, ha_val_node, entities_filename)
                    if new_content is None:
                        return
                elif isinstance(ha_val_node, yaml.ScalarNode) and ha_val_node.tag == "!include":
                    # homeassistant is delegated to an included file — patch that file instead.
                    include_path = Path(ha_val_node.value)
                    if include_path.is_absolute():
                        raise PersistentEntityError(
                            "Cannot append persistent entities: 'homeassistant: !include' must use a relative path inside the staged "
                            "Home Assistant configuration. Absolute include paths are not supported."
                        )
                    staged_root_abs = staged_config_root.resolve()
                    include_file = (staged_config_root / include_path).resolve()
                    if not include_file.is_relative_to(staged_root_abs):
                        raise PersistentEntityError(
                            "Cannot append persistent entities: 'homeassistant: !include' resolves outside the staged Home Assistant "
                            "configuration directory. Please use an include path within the staged config."
                        )
                    self._patch_homeassistant_include_file(include_file, entities_filename)
                    return
                elif isinstance(ha_val_node, yaml.ScalarNode) and ha_val_node.tag == "tag:yaml.org,2002:null":
                    # homeassistant: with no value — insert packages block after the key line.
                    ha_indent: int = ha_key_node.start_mark.column
                    child_col = ha_indent + 2
                    insert_at = ha_key_node.start_mark.line + 1
                    lines.insert(insert_at, f"{' ' * child_col}packages:")
                    lines.insert(insert_at + 1, f"{' ' * (child_col + 2)}test_harness: !include {entities_filename}")
                    new_content = "\n".join(lines).rstrip() + "\n"
                else:
                    raise PersistentEntityError(
                        "Cannot append persistent entities: 'homeassistant' must be a block mapping in configuration.yaml. "
                        "Please convert it to a block mapping before using ha_persistent_entities_path."
                    )
            else:
                # No homeassistant key — append a minimal homeassistant.packages block.
                new_content = content.rstrip() + f"\n\n# Harness: Include persistent entities package\nhomeassistant:\n  packages:\n    test_harness: !include {entities_filename}\n"

            with open(config_file, "w") as f:
                f.write(new_content)

            logger.debug(f"Patched configuration.yaml with homeassistant.packages.test_harness for {entities_filename}")
        except PersistentEntityError:
            raise
        except OSError as e:
            raise PersistentEntityError(f"Failed to patch configuration.yaml with persistent entities: {e}")

    @staticmethod
    def _block_end_line(node: yaml.Node) -> int:
        """Return the line index at which to insert content after a YAML block node."""
        end_line: int = node.end_mark.line
        end_col: int = node.end_mark.column
        return end_line if end_col == 0 else end_line + 1

    def _patch_packages_in_mapping(self, content: str, ha_mapping_node: yaml.MappingNode, entities_filename: str) -> Optional[str]:
        """Find and patch the packages key in a homeassistant block mapping.

        Handles all packages value forms: null/empty (inserts entry), block mapping
        (appends entry), flow-style mapping (rewrites to block then appends).

        Args:
            content: Text of the file containing ha_mapping_node.
            ha_mapping_node: The MappingNode that is the homeassistant block body.
            entities_filename: Name of the entities file to include.

        Returns:
            Patched content string, or None if test_harness is already present.

        Raises:
            PersistentEntityError: If packages has an unsupported structure.
        """
        if f"test_harness: !include {entities_filename}" in content:
            return None

        lines = content.splitlines()

        # Find the packages key in the mapping.
        pkg_key_node: Optional[yaml.ScalarNode] = None
        pkg_val_node: Optional[yaml.Node] = None
        for key_node, val_node in ha_mapping_node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "packages":
                pkg_key_node = key_node
                pkg_val_node = val_node
                break

        if pkg_key_node is None:
            # No packages key — derive child indentation from existing children, or default to parent col+2.
            child_col = ha_mapping_node.value[0][0].start_mark.column if ha_mapping_node.value else ha_mapping_node.start_mark.column + 2
            insert_at = self._block_end_line(ha_mapping_node)
            lines.insert(insert_at, f"{' ' * child_col}packages:")
            lines.insert(insert_at + 1, f"{' ' * (child_col + 2)}test_harness: !include {entities_filename}")
        elif isinstance(pkg_val_node, yaml.MappingNode):
            if pkg_val_node.flow_style:
                # Rewrite the single-line flow mapping to block style.
                for key_node, _ in pkg_val_node.value:
                    if isinstance(key_node, yaml.ScalarNode) and key_node.value == "test_harness":
                        return None
                pkg_col: int = pkg_key_node.start_mark.column
                pkg_child_col_flow: int = pkg_col + 2
                block_lines = [f"{' ' * pkg_col}packages:"]
                for key_node, val_node in pkg_val_node.value:
                    # Reconstruct each entry verbatim from the source (preserves tags like !include).
                    start_idx: int = key_node.start_mark.index
                    end_idx: int = val_node.end_mark.index
                    entry_text = content[start_idx:end_idx]
                    block_lines.append(f"{' ' * pkg_child_col_flow}{entry_text}")
                block_lines.append(f"{' ' * pkg_child_col_flow}test_harness: !include {entities_filename}")
                pkg_line: int = pkg_key_node.start_mark.line
                pkg_end_line_plus1: int = pkg_val_node.end_mark.line + 1
                lines[pkg_line:pkg_end_line_plus1] = block_lines
            else:
                # Block mapping — derive test_harness indent from first existing entry, or fallback.
                pkg_child_col: int = pkg_val_node.value[0][0].start_mark.column if pkg_val_node.value else pkg_key_node.start_mark.column + 2
                for key_node, _ in pkg_val_node.value:
                    if isinstance(key_node, yaml.ScalarNode) and key_node.value == "test_harness":
                        return None
                lines.insert(
                    self._block_end_line(pkg_val_node),
                    f"{' ' * pkg_child_col}test_harness: !include {entities_filename}",
                )
        elif isinstance(pkg_val_node, yaml.ScalarNode) and pkg_val_node.tag == "tag:yaml.org,2002:null":
            # packages: is present but empty — insert test_harness after the packages: line.
            lines.insert(
                pkg_key_node.start_mark.line + 1,
                f"{' ' * (pkg_key_node.start_mark.column + 2)}test_harness: !include {entities_filename}",
            )
        else:
            raise PersistentEntityError(
                "Cannot append persistent entities: existing 'homeassistant.packages' is not a block mapping. " "Please convert it to a block mapping before using ha_persistent_entities_path."
            )

        return "\n".join(lines).rstrip() + "\n"

    def _patch_homeassistant_include_file(self, include_file: Path, entities_filename: str) -> None:
        """Patch a homeassistant !include file to add packages.test_harness.

        When configuration.yaml uses `homeassistant: !include <file>`, the included
        file contains the homeassistant block body. This method patches that file to
        ensure `packages.test_harness` is present.

        Args:
            include_file: Path to the included homeassistant configuration file.
            entities_filename: Name of the entities file to include.

        Raises:
            PersistentEntityError: If the file cannot be read, parsed, or patched.
        """
        try:
            with open(include_file, "r") as f:
                content = f.read()

            if f"test_harness: !include {entities_filename}" in content:
                logger.debug(f"{include_file.name} already includes homeassistant.packages.test_harness")
                return

            try:
                root_node = yaml.compose(content, Loader=yaml.SafeLoader)
            except yaml.YAMLError as e:
                raise PersistentEntityError(f"Failed to parse homeassistant include file {include_file.name}: {e}")

            if not isinstance(root_node, yaml.MappingNode) or root_node.flow_style:
                raise PersistentEntityError(
                    f"Cannot append persistent entities: homeassistant include file '{include_file.name}' "
                    "must have a block mapping at root level. "
                    "Please convert it to a block mapping before using ha_persistent_entities_path."
                )

            new_content = self._patch_packages_in_mapping(content, root_node, entities_filename)
            if new_content is None:
                return

            with open(include_file, "w") as f:
                f.write(new_content)

            logger.debug(f"Patched {include_file.name} with homeassistant.packages.test_harness for {entities_filename}")
        except PersistentEntityError:
            raise
        except OSError as e:
            raise PersistentEntityError(f"Failed to patch homeassistant include file {include_file.name}: {e}")

    def _inject_custom_integration(self, staging_dir: Path) -> None:
        """Copy the bundled ha_test_harness custom integration into the staged config directory.

        Args:
            staging_dir: Root directory of staged HA config.

        Raises:
            PersistentEntityError: If copying the integration fails.
        """
        src = Path(__file__).parent / "custom_components" / "ha_test_harness"
        dst = staging_dir / "custom_components" / "ha_test_harness"
        try:
            dst.parent.mkdir(exist_ok=True)
            if dst.exists():
                logger.warning(
                    f"Staged config already contains a 'custom_components/ha_test_harness' directory at {dst}. "
                    "It will be overwritten by the bundled ha_test_harness integration. "
                    "Rename or remove the existing directory if this is not intended."
                )
            shutil.copytree(src, dst, dirs_exist_ok=True)
            logger.debug(f"Injected ha_test_harness custom integration into: {dst}")
        except (OSError, shutil.Error) as e:
            raise PersistentEntityError(f"Failed to inject ha_test_harness custom integration: {e}")

    def _inject_ha_test_harness_config(self, staging_dir: Path) -> None:
        """Append 'ha_test_harness:' top-level key to configuration.yaml if not already present.

        Args:
            staging_dir: Root directory of staged HA config.

        Raises:
            PersistentEntityError: If patching configuration.yaml fails.
        """
        config_file = staging_dir / "configuration.yaml"
        try:
            content = config_file.read_text()
            # Use a line-anchored regex to avoid matching commented-out lines (e.g. "# ha_test_harness:").
            if not re.search(r"^ha_test_harness:", content, re.MULTILINE):
                # Direct write is acceptable here: this is a staging directory that nothing else is
                # reading concurrently — the file is written once before containers start.
                config_file.write_text(content.rstrip() + "\n\nha_test_harness:\n")
                logger.debug("Appended ha_test_harness: to configuration.yaml")
        except OSError as e:
            raise PersistentEntityError(f"Failed to inject ha_test_harness config into configuration.yaml: {e}")

    def _detect_ha_config_root(self) -> Path:
        """Detect the Home Assistant configuration root directory.

        Checks the HOME_ASSISTANT_CONFIG_ROOT environment variable first.
        If not set, falls back to the 'home_assistant' subdirectory in the
        current working directory.

        Returns:
            Path: The detected Home Assistant configuration root directory.
        """
        env_var = os.environ.get("HOME_ASSISTANT_CONFIG_ROOT")
        if env_var:
            ha_root = Path(env_var)
            logger.debug(f"Using Home Assistant root from HOME_ASSISTANT_CONFIG_ROOT: {ha_root}")
            return ha_root

        ha_root = Path(os.getcwd()) / "home_assistant"
        logger.debug(f"HOME_ASSISTANT_CONFIG_ROOT not set, using default 'home_assistant' subdirectory as Home Assistant root: {ha_root}")
        return ha_root

    def _detect_appdaemon_config_root(self) -> Path:
        """Detect the AppDaemon configuration root directory.

        Checks the APPDAEMON_CONFIG_ROOT environment variable first.
        If not set, falls back to the 'appdaemon' subdirectory in the
        current working directory.

        Returns:
            Path: The detected AppDaemon configuration root directory.
        """
        env_var = os.environ.get("APPDAEMON_CONFIG_ROOT")
        if env_var:
            appdaemon_root = Path(env_var)
            logger.debug(f"Using AppDaemon root from APPDAEMON_CONFIG_ROOT: {appdaemon_root}")
            return appdaemon_root

        appdaemon_root = Path(os.getcwd()) / "appdaemon"
        logger.debug(f"APPDAEMON_CONFIG_ROOT not set, using default 'appdaemon' subdirectory as AppDaemon root: {appdaemon_root}")
        return appdaemon_root

    def start(self) -> None:
        """Start the Docker Compose test environment.

        Executes 'docker compose up -d --wait' which:
        - Starts Home Assistant on localhost:8123
        - Waits for Home Assistant to be healthy (via healthcheck)
        - Generates authentication token and AppDaemon config
        - Starts AppDaemon on localhost:5050
        - Waits for AppDaemon to be healthy (via healthcheck)

        Always stages the Home Assistant config directory to inject the bundled
        ha_test_harness custom integration, and also applies the persistent entities
        overlay if persistent entities are configured.

        Raises:
            DockerError: If the docker compose command fails or if the services
                fail to start properly.
            PersistentEntityError: If persistent entity configuration fails.
        """
        logger.debug("Starting docker-compose test environment...")
        try:
            # Always stage config to inject the bundled ha_test_harness integration
            # (and persistent entities overlay if configured).
            config_root = self._stage_ha_config_with_entities()

            # Set environment variables for docker-compose to mount the configuration directories
            env = os.environ.copy()
            env["HA_CONFIG_ROOT"] = str(config_root)
            env["APPDAEMON_CONFIG_ROOT"] = str(self._appdaemon_config_root)

            subprocess.run(
                ["docker", "compose", "-p", self._run_id, "up", "-d", "--wait"],
                cwd=self._containers_dir,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

            # Start monitoring containers
            self._containers = self._refresh_container_details()
            logger.debug("Docker-compose environment started successfully:")
            for container in self._containers.values():
                logger.debug(f"  - {container.service}: {container.name} (ID: {container.container_id}) - Status: {container.status}, Health: {container.health}")

        except subprocess.CalledProcessError as e:
            # Pull as much info as we can on the containers - even though they likely failed to start
            self._containers = self._refresh_container_details()

            error_msg = f"Failed to start docker-compose environment (project: {self._run_id}): {e}"
            if e.stderr:
                error_msg += f"\nStderr:\n{e.stderr}"
            if e.stdout:
                error_msg += f"\nStdout:\n{e.stdout}"

            # Include container logs for debugging
            error_msg += f"\n\n{self.get_container_diagnostics()}"

            raise DockerError(error_msg)
        except FileNotFoundError:
            raise DockerError("'docker' command not found. Ensure Docker is installed and available in PATH.")

    def stop(self) -> None:
        """Stop the Docker Compose test environment.

        Executes 'docker compose down -v' which:
        - Stops all running containers
        - Removes containers and volumes
        - Cleans up resources

        This method is safe to call multiple times; subsequent calls are
        no-ops if the environment is already stopped.

        Note:
            Any exceptions during shutdown are logged but not raised, ensuring
            cleanup can complete even if the environment is in an unexpected state.
        """
        if not self._containers:
            logger.debug("Containers already stopped, skipping")
        else:
            logger.debug("Stopping docker-compose test environment...")
            try:
                subprocess.run(
                    ["docker", "compose", "-p", self._run_id, "down", "-v"],
                    cwd=self._containers_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.debug("Docker-compose environment stopped successfully")
            except subprocess.CalledProcessError as e:
                error_msg = f"Failed to stop docker-compose environment (project: {self._run_id}): {e}"
                if e.stderr:
                    error_msg += f"\nStderr:\n{e.stderr}"
                if e.stdout:
                    error_msg += f"\nStdout:\n{e.stdout}"
                logger.warning(error_msg)
            except FileNotFoundError:
                logger.warning("'docker' command not found. Ensure Docker is installed and available in PATH.")
            finally:
                self._containers.clear()

        # Clean up staged config directory if it was created
        if self._staged_ha_config_root and self._staged_ha_config_root.exists():
            logger.debug(f"Cleaning up staged config directory: {self._staged_ha_config_root}")
            try:
                shutil.rmtree(self._staged_ha_config_root, ignore_errors=False)
            except Exception as e:
                logger.warning(f"Failed to clean up staged config directory: {e}")

    def _collect_docker_stats(self, logs: list[str]) -> None:
        """Collect CPU/memory usage via docker stats."""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"],
                cwd=self._containers_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            logs.append("\n========== DOCKER STATS ==========")
            logs.append(result.stdout)
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to get docker stats: {e}")

    def _collect_docker_inspect(self, logs: list[str]) -> None:
        """Collect detailed container state via docker inspect."""
        try:
            inspect_format = "{{.Name}}: State={{.State.Status}}, Restarts={{.RestartCount}}, ExitCode={{.State.ExitCode}}, OOMKilled={{.State.OOMKilled}}"
            for container in self._containers.values():
                result = subprocess.run(
                    ["docker", "inspect", "--format", inspect_format, container.container_id],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                logs.append(result.stdout.strip())
        except Exception as e:
            logs.append(f"** ERROR ** Failed to get docker inspect: {e}")

    def _collect_network_reachability(self, logs: list[str]) -> None:
        """Test network reachability to Home Assistant API."""
        try:
            ha_container = self._get_container("homeassistant")
            if ha_container and ha_container.url:
                logs.append("\n========== NETWORK REACHABILITY ==========")
                try:
                    response = requests.get(f"{ha_container.url}/api/", timeout=10)
                    logs.append(f"Home Assistant API reachable: HTTP {response.status_code}")
                except requests.Timeout:
                    logs.append("Home Assistant API UNREACHABLE: Request timed out after 10s")
                except requests.ConnectionError:
                    logs.append("Home Assistant API UNREACHABLE: Connection refused")
                except Exception as e:
                    logs.append(f"Home Assistant API UNREACHABLE: {e}")
        except Exception as e:
            logs.append(f"** ERROR ** Failed to test network reachability: {e}")

    def _require_ha_container(self, logs: list[str], purpose: str) -> Optional[DockerContainer]:
        """Get the HA container or log an error and return None."""
        ha_container = self._get_container("homeassistant")
        if not ha_container:
            logs.append(f"\n** ERROR ** HA container not found for {purpose}")
        return ha_container

    def _format_request_error(self, endpoint: str, error: Exception) -> str:
        """Format a request exception consistently."""
        if isinstance(error, requests.Timeout):
            return f"{endpoint}: TIMEOUT (>10s)"
        if isinstance(error, requests.ConnectionError):
            return f"{endpoint}: CONNECTION REFUSED"
        return f"{endpoint}: ERROR ({error})"

    def _collect_docker_network_state(self, logs: list[str]) -> None:
        """Capture Docker network inspect output for the test network."""
        try:
            network_name = f"{self._run_id}_default"
            result = subprocess.run(
                ["docker", "network", "inspect", network_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logs.append("\n========== DOCKER NETWORK STATE ==========")
            logs.append(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            logs.append(f"\n** ERROR ** Failed to inspect Docker network: {e.stderr.strip()}")
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to inspect Docker network: {e}")

    def _collect_tcp_connection_state(self, logs: list[str]) -> None:
        """Capture TCP socket statistics from inside the HA container."""
        try:
            ha_container = self._require_ha_container(logs, "TCP state collection")
            if not ha_container:
                return
            logs.append("\n========== TCP CONNECTION STATE (HA CONTAINER) ==========")
            result = subprocess.run(
                ["docker", "exec", ha_container.name, "sh", "-c", "netstat -tuln 2>/dev/null || ss -tuln 2>/dev/null || echo 'Neither netstat nor ss available in container'"],
                capture_output=True,
                text=True,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            logs.append(output)
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to collect TCP connection state: {e}")

    def _collect_multi_endpoint_api_probing(self, logs: list[str]) -> None:
        """Probe multiple HA API endpoints with response times."""
        try:
            ha_container = self._require_ha_container(logs, "API probing")
            if not ha_container or not ha_container.url:
                if ha_container is None:
                    return
                logs.append("\n** ERROR ** HA container URL not found for API probing")
                return
            logs.append("\n========== API ENDPOINT TESTS ==========")
            endpoints = ["/api/", "/api/states", "/"]
            for endpoint in endpoints:
                url = f"{ha_container.url}{endpoint}"
                try:
                    start = time.monotonic()
                    response = requests.get(url, timeout=10)
                    elapsed = time.monotonic() - start
                    logs.append(f"{endpoint}: HTTP {response.status_code} ({elapsed:.2f}s)")
                except Exception as e:
                    logs.append(self._format_request_error(endpoint, e))
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to probe API endpoints: {e}")

    def _collect_health_check_correlation(self, logs: list[str]) -> None:
        """Compare Docker health check status with actual API reachability."""
        try:
            ha_container = self._require_ha_container(logs, "health check correlation")
            if not ha_container:
                return
            logs.append("\n========== HEALTH CHECK VS API ==========")
            inspect_result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", ha_container.container_id],
                capture_output=True,
                text=True,
                check=True,
            )
            docker_health = inspect_result.stdout.strip()
            logs.append(f"Docker Health: {docker_health}")
            api_reachable = False
            if ha_container.url:
                try:
                    response = requests.get(f"{ha_container.url}/api/", timeout=5)
                    logs.append(f"API Reachable: yes (HTTP {response.status_code})")
                    api_reachable = True
                except Exception as e:
                    logs.append(f"API Reachable: no ({e})")
            else:
                logs.append("API Reachable: unknown (no URL)")
            docker_healthy = docker_health == "healthy"
            if docker_healthy == api_reachable:
                logs.append(f"Correlation: Docker health and API reachability agree (both {'healthy/reachable' if docker_healthy else 'unhealthy/unreachable'})")
            else:
                if docker_healthy:
                    logs.append("WARNING: Docker reports healthy but API is unreachable — health check may be insufficient")
                else:
                    logs.append("WARNING: Docker reports unhealthy but API is reachable — health check may be too strict")
        except subprocess.CalledProcessError as e:
            logs.append(f"\n** ERROR ** Failed to get Docker health status: {e.stderr.strip()}")
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to correlate health check: {e}")

    def _collect_extended_ha_logs(self, logs: list[str]) -> None:
        """Capture extended HA container logs (last 500 lines and last 2 minutes)."""
        try:
            ha_container = self._require_ha_container(logs, "extended logs")
            if not ha_container:
                return
            logs.append("\n========== EXTENDED HA LOGS (LAST 500 LINES + LAST 2 MINUTES) ==========")
            tail_result = subprocess.run(
                ["docker", "logs", "--tail=500", ha_container.container_id],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            since_result = subprocess.run(
                ["docker", "logs", "--since=2m", ha_container.container_id],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            tail_output = tail_result.stdout or tail_result.stderr or ""
            since_output = since_result.stdout or since_result.stderr or ""
            if tail_output or since_output:
                if tail_output:
                    logs.append("--- Last 500 lines ---")
                    logs.append(tail_output)
                if since_output:
                    logs.append("--- Last 2 minutes ---")
                    logs.append(since_output)
            else:
                logs.append("<<empty>>")
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to collect extended HA logs: {e}")

    def _collect_process_state(self, logs: list[str]) -> None:
        """Capture process state inside the HA container."""
        try:
            ha_container = self._require_ha_container(logs, "process state collection")
            if not ha_container:
                return
            logs.append("\n========== HA PROCESS STATE ==========")
            result = subprocess.run(
                ["docker", "exec", ha_container.name, "sh", "-c", "ps aux 2>/dev/null || ps -ef 2>/dev/null || echo 'ps not available in container'"],
                capture_output=True,
                text=True,
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            logs.append(output)
        except Exception as e:
            logs.append(f"\n** ERROR ** Failed to collect process state: {e}")

    def get_container_diagnostics(self, test_name: Optional[str] = None, test_duration: Optional[float] = None) -> str:
        """Dump logs and diagnostic information from all containers.

        Captures:
        - Container status and logs (last 200 lines)
        - Docker stats (CPU/memory usage)
        - Docker inspect (detailed state, restart count)
        - Network reachability test for Home Assistant API
        - Docker network state (network inspect)
        - TCP connection state inside HA container
        - Multi-endpoint API probing with response times
        - Health check vs API reachability correlation
        - Extended HA logs (last 500 lines)
        - Process state inside HA container
        - Current test name and duration (if provided)

        Args:
            test_name: Optional name of the test that triggered the diagnostics capture.
            test_duration: Optional duration of the test in seconds.

        Returns:
            A string containing container diagnostics for debugging.
        """
        logs = ["========== CONTAINER DIAGNOSTICS =========="]
        if test_name is not None:
            logs.append(f"Test: {test_name}")
            if test_duration is not None:
                logs.append(f"Duration: {test_duration:.2f}s")
        try:
            self._containers = self._refresh_container_details()
            for container in self._containers.values():
                logs.append(f"{container}")
        except Exception as e:
            logs.append(f"** ERROR ** Failed to dump container diagnostics: {e}")

        self._collect_docker_stats(logs)
        self._collect_docker_inspect(logs)
        self._collect_network_reachability(logs)
        self._collect_docker_network_state(logs)
        self._collect_tcp_connection_state(logs)
        self._collect_multi_endpoint_api_probing(logs)
        self._collect_health_check_correlation(logs)
        self._collect_extended_ha_logs(logs)
        self._collect_process_state(logs)

        logs.append("========== END DIAGNOSTICS ==========")
        return "\n".join(logs)

    def containers_healthy(self) -> bool:
        """Check if all containers are healthy.

        Returns:
            True if all containers are running and healthy, False otherwise.
        """
        if not self._containers:
            return False

        try:
            result = subprocess.run(
                ["docker", "compose", "-p", self._run_id, "ps", "--format", "json"],
                cwd=self._containers_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            # Docker compose returns one JSON object per line, not a JSON array
            containers = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    containers.append(json.loads(line))

            for container in containers:
                state = container.get("State", "").lower()
                health = container.get("Health", "").lower()

                # Container is unhealthy if not running or health check failing
                if state != "running" or (health and health != "healthy"):
                    logger.warning(f"Container {container.get('Name')} is unhealthy: state={state}, health={health}")
                    return False

            return True

        except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to check container health: {e}")
            return False

    def get_home_assistant_url(self) -> str:
        """Get the Home Assistant URL with dynamically assigned port.

        Returns:
            The full URL to Home Assistant (e.g., "http://localhost:49153").

        Raises:
            DockerError: If the port mapping cannot be determined.
        """
        container = self._get_container("homeassistant")
        if not container:
            raise DockerError("Home Assistant container not found")
        return container.url

    def get_appdaemon_url(self) -> str:
        """Get the AppDaemon URL with dynamically assigned port.

        Returns:
            The full URL to AppDaemon (e.g., "http://localhost:49154").

        Raises:
            DockerError: If the port mapping cannot be determined.
        """
        container = self._get_container("appdaemon")
        if not container:
            raise DockerError("AppDaemon container not found")
        return container.url

    def read_container_file(self, service: str, file_path: str) -> str:
        """Read a file from a running container.

        Args:
            service: The service name (e.g., "homeassistant", "appdaemon").
            file_path: The absolute path to the file inside the container.

        Returns:
            The contents of the file as a string.

        Raises:
            DockerError: If the file cannot be read from the container.
        """
        container = self._get_container(service)
        if not container:
            raise DockerError(f"No container found for service {service}")

        logger.debug(f"Reading file {file_path} from container {container.name}")
        try:
            result = subprocess.run(
                ["docker", "exec", container.name, "cat", file_path],
                capture_output=True,
                text=True,
                check=True,
            )
            content = result.stdout.strip()

            if not content:
                raise DockerError(f"File {file_path} in container {container.name} is empty")

            logger.debug(f"Successfully read file {file_path} from container {container.name}")
            return content

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to read file {file_path} from container {container.name}: {e}"
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr}"
            raise DockerError(error_msg)
        except FileNotFoundError:
            raise DockerError("'docker' command not found. Ensure Docker is installed and available in PATH.")

    def write_container_file(self, service: str, file_path: str, content: str) -> None:
        """Write content to a file in a running container.

        Uses atomic write operation (write to temp file, then move) to prevent
        partial reads during file updates.

        This method is a no-op if containers are not running, making it safe to
        call during teardown or in error states.

        Args:
            service: The service name (e.g., "homeassistant", "appdaemon").
            file_path: The absolute path to the file inside the container.
            content: The content to write to the file.

        Raises:
            DockerError: If the file cannot be written to the container.
        """
        if not self._containers or service not in self._containers:
            logger.debug(f"Skipping write to {file_path}: {service} container not available")
            return

        container = self._get_container(service)
        if not container:
            raise DockerError(f"No container found for service {service}")

        logger.debug(f"Writing file {file_path} to container {container.name}")
        try:
            # Atomic write: write to temp file via stdin, then move
            # Using stdin piping to avoid shell injection vulnerabilities
            # Shell-escape paths to prevent injection via file path parameters
            temp_path = f"{file_path}.tmp"
            escaped_temp_path = shlex.quote(temp_path)
            escaped_file_path = shlex.quote(file_path)
            subprocess.run(
                ["docker", "exec", "-i", container.name, "sh", "-c", f"cat > {escaped_temp_path} && mv {escaped_temp_path} {escaped_file_path}"],
                input=content,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(f"Successfully wrote file {file_path} to container {container.name}")
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to write file {file_path} to container {container.name}: {e}"
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr}"
            raise DockerError(error_msg)
        except FileNotFoundError:
            raise DockerError("'docker' command not found. Ensure Docker is installed and available in PATH.")

    def _refresh_container_details(self) -> dict[str, DockerContainer]:
        """Retrieve details of all running containers in the Docker Compose project.

        Returns:
            A list of DockerContainer objects representing each running container.
        """
        containers = {}
        try:
            result = subprocess.run(
                ["docker", "compose", "-p", self._run_id, "ps", "-a", "--format", "json"],
                cwd=self._containers_dir,
                capture_output=True,
                text=True,
                check=True,
            )

            # Docker compose returns one JSON object per line, not a JSON array
            container_details = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    container_details.append(json.loads(line))

            for details in container_details:
                container_id = details.get("ID")
                service = details.get("Service")

                local_port = None
                mapped_port = None
                ports = details.get("Ports", "")
                if ports:
                    # Match pattern: <host>:<host_port>-><container_port>/<protocol>
                    # E.g. '0.0.0.0:64865->5050/tcp, [::]:64865->5050/tcp'
                    match = re.search(r":(\d+)->(\d+)/", ports)
                    if match:
                        mapped_port = int(match.group(1))
                        local_port = int(match.group(2))

                # Get container logs (no tail limit for stopped/failed containers)
                logs_result = subprocess.run(
                    ["docker", "logs", "--tail=200", container_id],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

                containers[service] = DockerContainer(
                    service=service,
                    name=details.get("Name"),
                    container_id=container_id,
                    url=f"http://localhost:{mapped_port}" if mapped_port else "",
                    local_port=local_port,
                    mapped_port=mapped_port,
                    status=details.get("Status"),
                    health=details.get("Health"),
                    exit_code=details.get("ExitCode"),
                    std_out=logs_result.stdout or "<<empty>>",
                    std_err=logs_result.stderr or "<<empty>>",
                )

            return containers

        except (subprocess.CalledProcessError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to get container details: {e}")
            return {}

    def _get_container(self, service: str) -> Optional[DockerContainer]:
        """Get the DockerContainer object for a given service.

        Args:
            service: The service name (e.g., "homeassistant", "appdaemon").

        Returns:
            DockerContainer: The corresponding DockerContainer object or None if not found.
        """
        return self._containers.get(service, None)
