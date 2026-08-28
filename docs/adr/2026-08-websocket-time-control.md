# 🂡 WebSocket-based time control

> **Status:** Active
> **Issue:** [#174 — HA container becomes unresponsive after time jumps via libfaketime](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/174)
> **Date:** 2026-08
> **Supersedes:** [2026-08-defensive-stabilization-after-time-jumps](2026-08-defensive-stabilization-after-time-jumps.md)

## 🂢 Context

The libfaketime-based time control mechanism causes Home Assistant's asyncio
event loop to stall after time jumps, resulting in a ~36% failure rate in tests
that perform time jumps followed by API interactions. Defensive stabilization
(health check polling + API retries) was added as a workaround but masks
transient issues and adds latency.

The root cause is that libfaketime intercepts libc time calls at the process
level, which conflicts with HA's asyncio event loop that relies on monotonic
time progression for scheduling. When the system clock jumps forward, pending
timers in the event loop become stale, causing the loop to stall.

## 🂢 Decision

### Replace libfaketime with in-process time offset

Instead of intercepting system calls, apply a time offset within HA's Python
process. The offset is stored in `hass.data[DOMAIN]["time_offset"]` and applied
by patching four HA time functions:

- `homeassistant.util.dt.utcnow()`
- `homeassistant.util.dt.now()`
- `homeassistant.helpers.event.time_tracker_utcnow()`
- `homeassistant.helpers.event.time_tracker_timestamp()`

All four return `real_time + time_offset`.

**Alternatives considered:**

- **Continue with libfaketime + defensive stabilization**: Masks issues, adds latency, unreliable.
- **Mock HA's time at test level**: Doesn't affect HA internals, only test code.
- **Fork HA with custom time handling**: Maintenance burden, diverges from upstream.

**Rationale:** In-process offset is transparent to HA, doesn't interfere with
the asyncio event loop, and allows backward time travel (useful for testing).

### WebSocket commands for time control

Expose three WebSocket commands:

- `ha_test_harness/time/set` — Set absolute time (computes offset from real time).
- `ha_test_harness/time/advance` — Advance time by a relative offset (adds to existing offset).
- `ha_test_harness/time/get` — Get current fake time.

**Alternatives considered:**

- **REST API**: Requires additional HTTP endpoint setup, less consistent with existing virtual entity commands.
- **Service calls**: Services are fire-and-forget, don't return values. WebSocket commands support request/response.

**Rationale:** WebSocket commands are consistent with the existing
`ha_test_harness/entity/*` commands and support synchronous request/response.

### Fire timers via `loop._scheduled`

When time is advanced, iterate over `loop._scheduled` (the asyncio event loop's
heap of scheduled callbacks) and fire any timers that fall within the advanced
time window. This ensures automations triggered by time-based events execute
promptly.

A version guard checks the HA version to ensure `loop._scheduled` exists, as
this is an internal CPython implementation detail that may change.

**Alternatives considered:**

- **Wait for real time to catch up**: Defeats the purpose of time control.
- **Manually trigger automations**: Doesn't scale, requires knowledge of all time-based automations.

**Rationale:** Firing timers ensures time-based automations execute as expected
when time is advanced, maintaining test determinism.

### Remove defensive stabilization

With in-process time control, the asyncio event loop no longer stalls. Remove:

- Auto `check_health()` after time jumps (`on_time_set` callback).
- API retry logic (`_retry_on_transient_failure`).

Keep:

- `is_unresponsive` flag (still useful for detecting genuine HA crashes).
- `_skip_if_unresponsive` fixture (still useful for skipping tests when HA is down).
- `check_health()` public method (still useful for diagnostics).

**Rationale:** The defensive measures were workarounds for libfaketime's
side effects. With the root cause eliminated, the workarounds are unnecessary
and mask real issues.

### Rename `apply_faketime` to `apply_time_change`

The `TimeMachine` constructor parameter `apply_faketime` is renamed to
`apply_time_change` to reflect the new implementation. The parameter now
receives a callable that sends a WebSocket command to set the time offset,
rather than writing to a faketime timestamp file.

**Rationale:** The old name referenced the libfaketime implementation detail.
The new name is implementation-agnostic.

### Keep `fast_forward()` and `jump_to_next()` forward-only

Despite the new implementation supporting backward time travel, the public
`fast_forward()` and `jump_to_next()` methods remain forward-only by design.
This preserves the semantic contract that tests progress through time.

A temporary `temp_set_time()` method is added for backward time testing,
which will be removed before merge.

**Rationale:** Forward-only semantics prevent test interdependence and ensure
deterministic test execution. Backward time travel is a testing escape hatch,
not a public API feature.

## 🂢 Consequences

- **Positive:**
  - Eliminates the ~36% failure rate in time-jump tests
  - Removes latency from defensive stabilization (no more health check polling)
  - Enables backward time travel for testing edge cases
  - Simpler codebase (no libfaketime installation, no retry logic)
  - More accurate time control (in-process, no system call interception)

- **Negative:**
  - Requires patching HA internal functions (brittle to HA version changes)
  - `loop._scheduled` is a CPython implementation detail (may change)
  - Time offset is per-process (AppDaemon still uses real time)

- **Neutral:**
  - AppDaemon time control is not addressed (AppDaemon doesn't expose time APIs)
  - Version guard required for `loop._scheduled` access
  - `temp_set_time()` is a temporary escape hatch for backward time testing
