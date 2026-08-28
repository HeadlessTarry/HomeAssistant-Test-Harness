# 🂡 Defensive stabilization after time jumps

> **Status:** Superseded by [2026-08-websocket-time-control](2026-08-websocket-time-control.md)
> **Issue:** [#174 — HA container becomes unresponsive after time jumps via libfaketime](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/174)
> **Date:** 2026-08

## 🂢 Context

When time is advanced via libfaketime (used by the `time_machine` fixture),
Home Assistant's asyncio event loop can occasionally stall, making the container
unresponsive to API calls. This manifests as a ~36% failure rate in tests that
perform time jumps followed by API interactions.

The root cause is HA's internal timing mechanisms becoming confused when the
system clock jumps forward. The event loop may have pending timers that are now
in the past, or internal state that depends on monotonic time progression.

## 🂢 Decision

### Defensive stabilization: always stabilize after time jumps

After every time jump, automatically verify HA is responsive using health check polling before returning control to the test. This hides HA's asyncio quirks from test authors.

**Alternatives considered:**

- **Fixed sleep after time jumps**: Simple but wasteful — most of the time HA recovers in <100ms. A 2-second sleep would add significant latency to test suites.
- **Opt-in stabilization**: Requires test authors to remember to call stabilization manually. Error-prone and defeats the purpose of a test harness.

**Rationale:** Polling with exponential backoff gives fast recovery when HA is
healthy (first check at 100ms) while tolerating slower recovery (up to 10s).
Always-on ensures test authors don't need to think about it.

### Health check endpoint: GET /api/config

Use `/api/config` instead of `/api/` for health checks. The `/api/config` endpoint returns a JSON payload that validates the full request/response cycle, not just HTTP connectivity.

**Alternatives considered:**

- **GET /api/**: Returns 200/401 but doesn't validate JSON parsing. Lighter weight but less thorough.
- **WebSocket ping**: Requires persistent connection management. More complex for a health check.

**Rationale:** `/api/config` is a lightweight endpoint that exercises the full HTTP stack and returns parseable JSON, confirming HA is truly functional.

### Exponential backoff polling

Poll with exponential backoff: initial interval 0.1s, max interval 1s, total timeout 10s.

**Alternatives considered:**

- **Fixed interval polling** (e.g., every 500ms): Simpler but either too aggressive (wastes CPU) or too slow (delays feedback).
- **Linear backoff**: More predictable but doesn't adapt as well to different recovery times.

**Rationale:** Exponential backoff starts aggressive (catches fast recoveries)
and backs off gracefully (avoids hammering a struggling HA). The 10s timeout
balances test suite latency against giving HA enough time to recover.

### Automatic retry on API methods

All API methods retry with exponential backoff (0.5s, 1s, 2s), max 3 retries, on `Timeout` and `ConnectionError` only.

**Alternatives considered:**

- **No retries**: Tests fail immediately on transient issues. Unacceptable given the 36% failure rate.
- **Retry on all exceptions**: Masks real bugs. Only network-level transient errors should be retried.
- **Configurable retry logic**: Adds API complexity. The default behavior should work for all cases.

**Rationale:** Retrying on `Timeout` and `ConnectionError` handles the specific
failure mode observed (HA's event loop stalling temporarily). Other exceptions
indicate real bugs that should surface immediately.

### Unified backoff behavior

Both health checks and API retries use exponential backoff, providing consistent timing behavior across the codebase.

**Rationale:** Consistency reduces cognitive load. Test authors don't need to understand different backoff strategies for different failure modes.

### Harness fixture wiring

The `time_machine` fixture wires `on_time_set` → `home_assistant.check_health()` automatically. This ensures stabilization happens transparently after every time jump.

**Alternatives considered:**

- **Manual stabilization in tests**: Test authors must remember to call `check_health()` after time jumps. Error-prone.
- **Separate `stabilize()` method**: Explicit but adds boilerplate to every test that uses time jumps.

**Rationale:** Automatic wiring via the fixture ensures stabilization is never forgotten. The `on_time_set` callback is already designed for post-time-change hooks.

## 🂢 Consequences

- **Positive:**
  - Eliminates the ~36% failure rate in time-jump tests
  - Test authors don't need to think about HA's asyncio quirks
  - Consistent behavior across all time manipulation operations
  - Fast recovery when HA is healthy (first check at 100ms)

- **Negative:**
  - Adds latency to time jumps when HA is slow to recover (up to 10s)
  - Health check polling adds load to HA during recovery
  - Retry logic masks transient issues that might indicate real bugs

- **Neutral:**
  - Stabilization is not configurable (always on)
  - Only `Timeout` and `ConnectionError` are retried (other exceptions surface immediately)
  - `/api/config` endpoint is used for health checks (not `/api/`)
