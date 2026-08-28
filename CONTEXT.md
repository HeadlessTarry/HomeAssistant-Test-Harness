# Home Assistant Integration Test Harness

A pytest plugin that enables integration testing of Home Assistant configurations (automations, templates, scripts, custom entities) against a real but isolated HA instance running in Docker.

## Language

**Test harness**:
The pytest plugin itself — the thing that orchestrates Docker, API clients, virtual entities, and time manipulation to enable testing against a real HA instance.
_Avoid_: Test framework, test library

**Virtual entity**:
A fake entity registered with HA at runtime via websocket commands during test execution.
Created programmatically per-test, destroyed after the test completes.
Provides minimal implementation to satisfy test needs without mocking HA's entity system.
_Avoid_: Mock entity, test entity, dynamic entity

**Session-scoped entity**:
An entity defined in YAML by the downstream project, registered with HA during startup (before HA comes online).
Available to all tests in the session.
Currently implemented as "persistent entities" via `ha_persistent_entities_path` config.
_Avoid_: Persistent entity, pre-registered entity, bootstrap entity

**Real entity**:
An entity that exists in HA without the harness — from the user's production config, HA native entities (sun.sun, zone.home), or integration-provided entities.
_Avoid_: Production entity, live entity

**Configuration under test**:
The Home Assistant configuration (YAML files for automations, templates, scripts, etc.) deployed into the HA instance.
This is the combination of the downstream project's configuration files and the running HA instance that interprets them.
_Avoid_: HA config, test subject, system under test

**Injected state**:
State set via `set_state()` on any entity (virtual or real). Automatically rolled back after each test to prevent state leakage.
_Avoid_: Synthetic state, fake state, test state

**Test rollback**:
The automatic cleanup that occurs after each test. Virtual entities are destroyed; real and session-scoped entities have their state and config restored to pre-test values.
_Avoid_: Cleanup, teardown, reset

**Deploying configuration**:
Copying HA config files (automations, templates, scripts, session-scoped entity definitions) into the Docker instance during startup, so HA reads them on initialization.
_Avoid_: Deploying config, installing config, loading config

**Dynamically registering virtual entities**:
Creating virtual entities at runtime via websocket commands during test execution, as opposed to deploying configuration at startup.
_Avoid_: Creating test entities, adding entities

**Injecting state**:
Setting entity state via `set_state()` on any entity (virtual or real). Automatically rolled back after each test.
_Avoid_: Manipulating state, faking state, overriding state

**Asserting entity state**:
Verifying that an entity's state or attributes match expected values after triggering an action or deploying configuration.
_Avoid_: Checking state, validating state, verifying state

**Downstream project**:
A project that consumes the test harness to validate its own Home Assistant configuration. Provides configuration files, session-scoped entity definitions, and test scenarios.
_Aliases_: client project, test suite

**Test environment**:
The isolated execution context for tests — a Docker container running Home Assistant with deployed configuration. Created at session start, destroyed at session end.
_Note_: Docker container is the infrastructure; HA instance is the application running inside it.

**Assertion diagnostics**:
Automatic capture of state change history when `assert_entity_state` fails.
Queries the History API from test-start to assertion-failure, formats the transitions with timestamps and attribute deltas, and appends to the AssertionError message.
_Avoid_: Failure diagnostics, error context, debug output

**State change history**:
A sequence of state/attribute transitions for an entity during a test, captured via the History API.
Each transition includes: timestamp (relative to test-start + absolute), new state value, and attribute deltas (changed/added/removed attributes).
_Avoid_: State log, event history, transition log

**Test start time**:
The timestamp captured at the start of each test (via `pytest_runtest_setup` hook). Used as the start of the History API query window for assertion diagnostics.
_Avoid_: Test begin time, fixture start time

**Stabilization**:
_Defined term removed._ Previously referred to health check polling after time jumps.
With WebSocket-based time control replacing libfaketime, HA's asyncio event loop no longer
stalls after time manipulation, making defensive stabilization unnecessary.
The `check_health()` method and `is_unresponsive` flag remain for detecting genuine HA crashes.
_Avoid_: Health check, recovery, wait period

## Design Principles

**Test isolation**:
Each test must be independent and not affected by other tests. This is achieved through Docker isolation (separate HA instance per test session) and automatic state rollback after each test.

## Known Discrepancies

- **persistent entities** vs **session-scoped entities**:
  The code and config files use "persistent entities" (e.g., `ha_persistent_entities_path`),
  but the domain term is "session-scoped entities".
  This naming inconsistency should be addressed in a future refactor.
