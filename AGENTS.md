# AGENTS.md

This file provides guidance to OpenCode when working with code in this repository.

## 🧩 What This Is

A pytest plugin (`ha_integration_test_harness`) for integration testing Home Assistant and AppDaemon
configurations using real Docker containers — no mocks. Tests run against a live HA instance managed
by the harness.

## ⚙️ Commands

```bash
# Initial setup (installs deps via uv, sets up pre-commit, creates .env)
./setup_dev_env.sh

# Full validation: pre-commit hooks + build + install test + example tests
./run_checks.sh

# Run example tests only
pytest examples/

# Run a single example test
pytest examples/test_basic_usage.py::test_entity_state_with_auto_cleanup

# Individual checks
black src/ && isort src/   # format
flake8 src/                 # lint
mypy src/                   # type check (strict mode)
python -m build             # build package
```

## 🏗️ Architecture

The package is a thin pytest plugin layered over Docker and the Home Assistant REST/WebSocket API:

```text
Tests (examples/) → Pytest plugin (conftest.py) → Client libraries → Docker containers
```

### Fixture dependency graph

```directory
docker (session)
  └─ home_assistant (session)
       └─ time_machine (session)
  └─ _cleanup_test_entities (function, autouse) [conditionally restores config + deletes entities]
```

`docker` stages the HA config into a temp dir, injects the bundled `ha_test_harness` custom
integration, then starts Docker Compose. `home_assistant` reads the long-lived token from the
container after it starts.

### Key components

- **[conftest.py](src/ha_integration_test_harness/conftest.py)** — Four session-scoped fixtures
  (`docker`, `home_assistant`, `app_daemon`, `time_machine`) and a function-scoped autouse fixture
  `_cleanup_test_entities` that calls `restore_entity_config()` then `clean_up_test_entities()` after
  each test (only if the test used the `home_assistant` fixture).

- **[docker_manager.py](src/ha_integration_test_harness/docker_manager.py)** — Orchestrates Docker
  Compose. Auto-discovers HA config from `HOME_ASSISTANT_CONFIG_ROOT` env var or `home_assistant/`
  subdirectory, and AppDaemon config from `APPDAEMON_CONFIG_ROOT` or `appdaemon/`. **Always** stages
  config: injects the bundled `ha_test_harness` custom integration into `custom_components/`, appends
  `ha_test_harness:` to `configuration.yaml`, and optionally applies the persistent entities YAML
  overlay. Handles ephemeral ports for parallel test support.

- **[custom_components/ha_test_harness/](src/ha_integration_test_harness/custom_components/ha_test_harness/)** —
  Bundled HA custom integration. Injected into every staged config at container startup. Exposes
  three WebSocket commands: `ha_test_harness/entity/create`, `ha_test_harness/entity/set_state`,
  `ha_test_harness/entity/delete`. Entities created via this integration are fully registered in the
  HA entity registry (have a `unique_id`, appear in the UI). Supported domains: `sensor`,
  `binary_sensor`, `switch`, `light` (defined in `SUPPORTED_DOMAINS` in `__init__.py`).

- **[homeassistant_client.py](src/ha_integration_test_harness/homeassistant_client.py)** — REST +
  WebSocket API client. Key methods: `set_state()`, `get_state()`, `remove_entity()`,
  `call_action()`, `assert_entity_state()` (polls until match or timeout), `given_an_entity()`
  (creates registered entity via `ha_test_harness` WebSocket + tracks for auto-cleanup),
  `given_entity_has()` (assigns area/labels via entity registry WebSocket + snapshots original
  config for rollback). **Routing:** entities in `_created_entities` → WebSocket (`ha_test_harness`)
  for state/delete; others → REST fallback. WebSocket opens a new connection per call, performs the
  auth handshake, then sends/receives the command.

- **[time_machine.py](src/ha_integration_test_harness/time_machine.py)** — Manipulates time via
  libfaketime. **Time can only move forward, never backward.** Session-scoped — clock persists
  across all tests. Methods: `fast_forward(delta)`, `jump_to_next(...)`,
  `advance_to_preset("sunrise"|"sunset")`. When constructed with a `timezone` (sourced from HA
  config), `hour`/`minute`/`second` in `jump_to_next` are interpreted as local wall-clock time with
  full DST handling.

- **[exceptions.py](src/ha_integration_test_harness/exceptions.py)** — Custom hierarchy:
  `IntegrationTestError` → `DockerError`, `HomeAssistantClientError`, `AppDaemonClientError`,
  `TimeMachineError`, `PersistentEntityError`. Always raise from this hierarchy, never bare
  `Exception`.

- **[containers/](src/ha_integration_test_harness/containers/)** — Docker Compose service
  definitions and setup scripts. The shared volume at `/shared_data/` carries tokens and time state
  between containers. File-based health markers (`.homeassistant_ready`) signal startup completion.

## 🧪 Testing Strategy

There are **no unit tests** — the package is a thin wrapper around Docker/APIs. All testing is done
via example tests in `examples/` against real containers. CI mirrors `./run_checks.sh`.

## 🎨 Code Style

- Line length: 200 characters (Black + isort black profile)
- Type hints required on all public APIs; mypy runs in **strict** mode
- Docstrings: Google style (`Args:`, `Returns:`, `Raises:`)
- Private methods/attributes use leading underscore

## ✍️ Writing Tests

**Prefer `given_an_entity()` for test entities** — creates registered entities (have `unique_id`, appear
in the HA UI) and tracks them for auto-cleanup. Supported domains: `sensor`, `binary_sensor`,
`switch`, `light`. Can be combined with `given_entity_has()` in the same test:

```python
home_assistant.given_an_entity("sensor.test", "42", attributes={"unit_of_measurement": "°C"})
home_assistant.given_an_entity("light.test", "off")
home_assistant.given_entity_has("light.test", area="living_room", labels=["night_mode"])
```

**Use `set_state()` only for raw state injection** (e.g. providing a synthetic reading that an automation
consumes). REST-injected entities are not registered in the entity registry and cannot be used with `given_entity_has()`.

**Use `call_action()` for derived entities** (template sensors, lights backed by `input_boolean`) —
`set_state()` has no effect on derived entities since HA recomputes them from the source.

**Use `assert_entity_state()` with `timeout`** for async state transitions:

```python
home_assistant.assert_entity_state("light.living_room", "on", timeout=10)
home_assistant.assert_entity_state("sensor.temp", expected_attributes={"min": lambda v: float(v) >= 10})
```

**Time machine:** Only request the `time_machine` fixture in tests that actually need it. Always
advance to explicit conditions in each test — the clock does not reset. Every test that depends on
time must advance to its own desired starting point.

## ➕ Adding a New Fixture

1. Define in `conftest.py` with Google-style docstring
2. Export from `__init__.py`
3. Document in `documentation/fixtures.md`
4. Add usage example in `documentation/usage.md`

## 🐳 Modifying Docker Configuration

1. Update [docker-compose.yaml](src/ha_integration_test_harness/containers/docker-compose.yaml)
2. Test manually: `export REPO_ROOT=/path/to/ha/config && docker compose up`
3. Update related setup scripts (`homeassistant/entrypoint.sh`, etc.)

## 📚 Documentation

Each topic lives in its own file under `documentation/`. New files must be linked from `README.md`.
Keep each file focused on one topic — split rather than grow a single file. Cross-link from related
files where useful.

Style: relative links between docs, fenced code blocks with explicit language tags, ≤200 char lines,
one blank line between each top-level heading and its content.

## ⚠️ Important Constraints

- **Package name**: Always `ha_integration_test_harness` (underscores, not hyphens)
- **Runtime dependencies**: Only `requests`, `python-dateutil`, `PyYAML`, `websocket-client` —
  avoid adding new ones without strong justification
- **Config mounts are read-write** (not `:ro`) — HA needs to write to its config directory
- **Error messages** for configuration problems must include the GitHub usage docs link for
  self-diagnosis
- **Atomic file writes**: Use temp-file-then-move for files that must not be seen in a partial state
