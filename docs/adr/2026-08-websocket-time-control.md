# 🂡 WebSocket-based time control

> **Status:** Active
> **Issue:** [#174 — HA container becomes unresponsive after time jumps via libfaketime](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/174)
> **Amended by:** [#178 — clock coherence under WebSocket time control](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/178)
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
process. The offset is stored in `hass.data[DOMAIN]["time_offset"]`.

**Patch every wall clock HA can read, and only the wall clock.** Home Assistant
reads the time through several unrelated routes. They must all agree: where they
disagree, HA compares a fake timestamp against a real one and concludes that
hours have passed when they have not. Issue #178 was three separate instances of
exactly that. The routes are:

- `time.time()`, read directly by `homeassistant.core` (state and event
  timestamps), `homeassistant.helpers.event` and `homeassistant.helpers.ratelimit`.
  Patching this covers the whole group process-wide, including callers we have
  not had to enumerate.
- `homeassistant.helpers.entity.timer`, a module-level alias of `time.time` bound
  at import time, which stamps every entity state write. Aliases bound at import
  cannot be reached by patching `time.time`, so they are re-pointed individually.
- `homeassistant.util.dt.utcnow()` / `now()`, which call `datetime.now()` rather
  than `time.time()` and so need replacing separately.
- `homeassistant.helpers.event.time_tracker_utcnow()` / `time_tracker_timestamp()`.

**`time.monotonic()` is deliberately left real.** asyncio and aiohttp schedule
callbacks and measure timeouts against the monotonic clock. Leaving it alone is
what keeps the event loop and the WebSocket connection carrying these very
commands working while wall-clock time moves.

**Alternatives considered:**

- **Continue with libfaketime + defensive stabilization**: Masks issues, adds latency, unreliable.
- **Mock HA's time at test level**: Doesn't affect HA internals, only test code.
- **Fork HA with custom time handling**: Maintenance burden, diverges from upstream.

**Rationale:** An in-process offset does not interfere with the asyncio event
loop, and confining it to the wall clock keeps the loop's own scheduling intact.

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

### Advance pending deadlines in `loop._scheduled` rather than firing callbacks

Callbacks are scheduled with `loop.call_at`, which measures against the monotonic
clock. The monotonic clock does not move when fake time does, so without help a
`delay: 00:30:00` would wait thirty real minutes and a time trigger three fake
hours away would never arrive.

Because `time.time()` is patched, both of HA's scheduling styles express their
deadline as a fake-time duration from the moment they were scheduled:

- relative, e.g. `async_call_later` and script `delay:` —
  `call_at(loop.time() + duration)`
- absolute, e.g. `async_track_point_in_utc_time` and HA timer entities —
  `call_at(loop.time() + target_timestamp - time.time())`

So on each time change, **subtract the offset delta from every pending Home
Assistant deadline**. This is correct for both styles, and a callback becomes due
exactly when that much fake time has elapsed. Once a deadline is in the past the
event loop runs it itself, in order, with normal exception handling.

Only Home Assistant's own timers are moved, identified by the callback's
`__module__`. The loop also holds timers for aiohttp — including the heartbeat and
timeout of the connection the command arrived on — plus asyncio, zeroconf and
bluetooth. Moving those makes aiohttp conclude the connection died mid-request,
which surfaces to the test as a connection timeout.

A runtime attribute check guards `loop._scheduled`, an internal CPython detail, so
that it degrades to a warning rather than crashing if it disappears.

**Alternatives considered:**

- **Invoke due callbacks by hand** (the original approach): requires deciding
  whether each deadline is due, which needs a different comparison for relative
  and absolute timers. The single comparison used compared deadlines against the
  *total accumulated* offset rather than elapsed time, so once a session had
  banked an offset, every timer scheduled within it fired on every subsequent
  advance, however small. It also meant reaching into `_callback`, `_args` and
  `_context` to run callbacks manually.
- **Wait for real time to catch up**: Defeats the purpose of time control.
- **Manually trigger automations**: Doesn't scale, requires knowledge of all time-based automations.

### Bound the wait for effects to land

After a time change the handler lets the resulting work run before replying, but
it must not use an unbounded `hass.async_block_till_done()`. That waits for every
tracked task, and an automation part-way through a `delay:` step is such a task.
Its delay can only elapse when fake time advances again, which cannot happen
while the handler is still holding the connection that would deliver the next
time command — so it deadlocks until the client's socket times out.

The wait is therefore bounded. Cancelling `async_block_till_done()` only abandons
its `asyncio.wait`; the tasks themselves keep running.

**Rationale:** Preserves the common case (let automations finish before replying)
while returning promptly when something is deliberately asleep.

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

The public `fast_forward()` and `jump_to_next()` methods are forward-only by
design. This preserves the semantic contract that tests progress through time.

Forward-only is not merely a stylistic contract: HA's recurring time listeners
arm themselves against absolute targets, so moving the clock backwards leaves
them armed in the future. An entity driven by a `time_pattern` trigger will
legitimately keep reporting its last value until the clock catches up again.
Deadlines are therefore only advanced when the offset increases.

**Rationale:** Forward-only semantics prevent test interdependence and ensure
deterministic test execution.

## 🂢 Consequences

- **Positive:**
  - Eliminates the ~36% failure rate in time-jump tests
  - Removes latency from defensive stabilization (no more health check polling)
  - Simpler codebase (no libfaketime installation, no retry logic)
  - More accurate time control (in-process, no system call interception)

- **Negative:**
  - Requires patching HA internal functions (brittle to HA version changes)
  - `loop._scheduled` and `TimerHandle._when` are CPython implementation details (may change)
  - `time.time()` is patched process-wide, so any library in the HA process sees fake wall-clock time
  - Time offset is per-process (AppDaemon still uses real time)
  - Moving the clock backwards leaves HA's recurring time listeners armed in the future

- **Neutral:**
  - AppDaemon time control is not addressed (AppDaemon doesn't expose time APIs)
  - Runtime attribute guard required for `loop._scheduled` access
  - Timers belonging to aiohttp, asyncio and other non-HA libraries stay on the real
    clock, which is also the clock they measure against
