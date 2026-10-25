"""End-to-end tests of session-level behaviour, run as separate downstream pytest sessions via pytester.

Each test builds a scratch downstream project (pytest.ini, home_assistant/) and runs pytest
in a subprocess against it. This covers what a single examples session cannot: config auto-discovery from the
working directory, pytest ini options, startup failures, and container teardown.
"""

import json
import subprocess
import threading
from pathlib import Path

import pytest

CONFIG_ROOT_ENV_VARS = ("HOME_ASSISTANT_CONFIG_ROOT", "HA_IMAGE")
TEMP_ENV_VARS = ("TMPDIR", "TEMP", "TMP")


def _containers_mounting(temp_dir: Path) -> set[str]:
    """Names of harness Home Assistant containers whose staged /config mount lives under ``temp_dir``."""
    ids = subprocess.run(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.service=homeassistant"], capture_output=True, text=True).stdout.split()
    if not ids:
        return set()
    inspected = json.loads(subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True).stdout or "[]")
    target = str(temp_dir).replace("\\", "/").lower() + "/"
    return {c["Name"] for c in inspected for m in c["Mounts"] if m["Destination"] == "/config" and m["Source"].replace("\\", "/").lower().startswith(target)}


def _run_downstream_session(pytester: pytest.Pytester) -> tuple[pytest.RunResult, set[str]]:
    """Run pytest in the scratch project, returning the result and every container it was seen to start."""
    temp_dir = pytester.path / "tmp"
    seen: set[str] = set()
    done = threading.Event()

    def watch() -> None:
        while not done.wait(2):
            seen.update(_containers_mounting(temp_dir))

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    try:
        result = pytester.runpytest_subprocess("-p", "no:cacheprovider", timeout=600)
    finally:
        done.set()
        watcher.join()
    return result, seen


@pytest.fixture
def downstream(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A scratch downstream project with no config-root env vars, so the harness must auto-discover it.

    Its temp dir is redirected into the project, so the staged HA config each session mounts identifies
    that session's containers.
    """
    for var in CONFIG_ROOT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    temp_dir = pytester.path / "tmp"
    temp_dir.mkdir()
    for var in TEMP_ENV_VARS:
        monkeypatch.setenv(var, str(temp_dir))
    return pytester


def _write_ha_config(project: Path, configuration_yaml: str, files: dict[str, str] | None = None) -> None:
    ha_root = project / "home_assistant"
    for rel, content in {"configuration.yaml": configuration_yaml, **(files or {})}.items():
        (ha_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (ha_root / rel).write_text(content)


def test_downstream_session_discovers_config_honours_exclusions_and_tears_down(downstream: pytest.Pytester) -> None:
    """A downstream project's config is found from the working directory, excluded files are not deployed,
    and containers are removed at session end even when a test fails."""
    _write_ha_config(
        downstream.path,
        "default_config:\n\nhomeassistant:\n  packages: !include_dir_named packages\n",
        {
            "packages/kept.yaml": "input_boolean:\n  kept:\n    initial: false\n",
            "packages/excluded.yaml": "input_boolean:\n  excluded:\n    initial: false\n",
        },
    )
    downstream.makefile(".ini", pytest="[pytest]\nha_exclude_files = packages/excluded.yaml\n")
    downstream.makepyfile(test_downstream="""
        def test_config_deployed_without_excluded_file(home_assistant):
            home_assistant.assert_entity_state("input_boolean.kept", "off")
            assert home_assistant.get_state("input_boolean.excluded") is None

        def test_failing_test(home_assistant):
            assert False, "deliberate failure"
        """)

    result, seen = _run_downstream_session(downstream)

    result.assert_outcomes(passed=1, failed=1)
    assert len(seen) == 1, f"expected one Home Assistant container for this session, saw {seen}"
    assert _containers_mounting(downstream.path / "tmp") == set(), "containers were not torn down"


def test_session_without_harness_fixtures_starts_no_containers(downstream: pytest.Pytester) -> None:
    """Tests that request no harness fixture must not start Docker."""
    _write_ha_config(downstream.path, "default_config:\n")
    downstream.makepyfile(test_plain="def test_plain():\n    assert True\n")

    result, seen = _run_downstream_session(downstream)

    result.assert_outcomes(passed=1)
    assert seen == set()


def test_missing_configuration_yaml_fails_at_startup(downstream: pytest.Pytester) -> None:
    """Without home_assistant/configuration.yaml the session errors clearly and starts nothing."""
    downstream.makepyfile(test_needs_ha="def test_needs_ha(home_assistant):\n    pass\n")

    result, seen = _run_downstream_session(downstream)

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*configuration.yaml not found at*"])
    assert seen == set()


def test_missing_persistent_entities_file_fails_at_startup(downstream: pytest.Pytester) -> None:
    """A ha_persistent_entities_path that does not exist errors before any container starts."""
    _write_ha_config(downstream.path, "default_config:\n")
    downstream.makefile(".ini", pytest="[pytest]\nha_persistent_entities_path = missing.yaml\n")
    downstream.makepyfile(test_needs_ha="def test_needs_ha(home_assistant):\n    pass\n")

    result, seen = _run_downstream_session(downstream)

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*Persistent entities file not found*missing.yaml*"])
    assert seen == set()


def test_ha_image_env_var_overrides_ini_and_reaches_docker(downstream: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    """HA_IMAGE beats the ha_image ini option, and the chosen image is what Docker is asked to run.

    Both references are deliberately invalid (uppercase repository names), so Docker rejects the env one
    without contacting a registry, and the proof is its error naming that reference.
    """
    ini_image = "Harness-Test-INI-Image:invalid"
    env_image = "Harness-Test-ENV-Image:invalid"
    _write_ha_config(downstream.path, "default_config:\n")
    downstream.makefile(".ini", pytest=f"[pytest]\nha_image = {ini_image}\n")
    downstream.makepyfile(test_needs_ha="def test_needs_ha(home_assistant):\n    pass\n")
    monkeypatch.setenv("HA_IMAGE", env_image)

    result, _ = _run_downstream_session(downstream)

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines([f"*unable to get image '{env_image}'*must be lowercase*"])
    assert ini_image not in result.stdout.str()
    assert _containers_mounting(downstream.path / "tmp") == set()
