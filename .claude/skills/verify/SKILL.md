---
name: verify
description: >-
  Experiment with the ha_integration_test_harness plugin from a throwaway downstream project against real HA and AppDaemon containers,
  without editing the repo's tests. Use to try a change, reproduce a bug, or see what a downstream user sees before writing a test in examples/.
---

# Verify the harness by experiment

The harness is a pytest plugin. Its user runs `pytest` in a repo that has `home_assistant/configuration.yaml` and `appdaemon/apps/`. To experiment, make a
throwaway repo like that and run `pytest` in it. Lasting checks belong in `examples/`. `examples/test_downstream_sessions.py` shows the same approach as
permanent `pytester` tests.

## Setup

Run `./setup_dev_env.sh --skip-checks` one time per checkout. It installs `src/` in editable mode, so your edits take effect on the next run.

Check that you are testing this checkout and that Docker is up:

```bash
uv run python -c "import ha_integration_test_harness as h; print(h.__file__)"   # must be under this checkout's src/
docker info --format '{{.ServerVersion}}'
```

## Run an experiment

Create a scratch project under `.verify/` (gitignored):

```text
.verify/<name>/
├── pytest.ini                        # [pytest] plus any plugin options (ha_image, ha_exclude_files, ha_persistent_entities_path)
├── home_assistant/configuration.yaml # default_config: plus the automations or helpers under test
├── appdaemon/apps/apps.yaml          # can be just a comment
└── test_experiment.py                # uses home_assistant, time_machine, app_daemon, docker fixtures
```

`pytest.ini` is required. Without it, pytest walks up to the repo's `pyproject.toml` and uses its settings.

Run it from inside the scratch project:

```bash
cd .verify/<name> && env -u HOME_ASSISTANT_CONFIG_ROOT -u APPDAEMON_CONFIG_ROOT uv run pytest -p no:cacheprovider --log-cli-level=INFO
```

- The `env -u` removes the config-root variables. If they are set (for example from the repo's `.env`), the plugin uses `examples/` instead of your scratch
  config.
- A run takes about 30 s when images are cached. The log line `Docker containers started successfully` means HA and AppDaemon are up. At session end the
  plugin removes its containers, even when tests fail.
- To try a specific HA version, set `HA_IMAGE=homeassistant/home-assistant:<tag>` or add `ha_image = ...` to `pytest.ini`.

The docs describe each fixture and method: `docs/home-assistant-fixture.md`, `docs/time-machine-fixture.md`, and `docs/persistent-entities.md`. Copy test
patterns from `examples/`.

## What counts as proof

- The scratch test uses only the public API from `ha_integration_test_harness` and the fixtures. Do not use `_private` methods.
- The pytest output shows the action ran against live containers and the expected end state.
- Break the expectation one time and confirm the test fails. A test that only ever passed proves nothing.

## Cleanup

Delete `.verify/<name>/` when you are done. Each harness session cleans up its own containers. Other sessions on the same machine also run harness
containers, so never remove containers by name pattern.

If a run was interrupted (Ctrl-C, killed shell), its containers keep running. Find them by their AppDaemon apps mount, which points at your scratch project:

```bash
docker inspect $(docker ps -aq --filter label=com.docker.compose.service=appdaemon) \
  --format '{{index .Config.Labels "com.docker.compose.project"}} {{range .Mounts}}{{if eq .Destination "/conf/apps"}}{{.Source}}{{end}}{{end}}'
docker compose -p <project-id-whose-mount-is-your-.verify-dir> down -v
```

## When the experiment works

If the behavior is worth keeping, add a test to `examples/`. Use `examples/test_downstream_sessions.py` (pytester) for session-level behavior such as config
discovery, ini options, startup failures, and teardown. Use a normal fixture-based test for everything else. Then run `./run_checks.sh`.
