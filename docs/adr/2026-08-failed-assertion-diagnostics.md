# Failed assertion diagnostics via History API

> **Status:** Active
> **Issue:** [#120 — Failed entity-state assertion diagnostics](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/120)
> **Date:** 2026-08

## Context

When `assert_entity_state` fails, the error message shows only the current state and expected state. This makes it difficult to diagnose:

- What state transitions occurred during the test
- Whether an automation fired at the wrong time
- Whether state was injected correctly
- Why intermittent failures occur (e.g. race conditions)

The issue requested capturing state change history since test-start, plus what triggered each change.

## Decision

### Data source: History API

Use the REST History API (`/api/history/period/{start}?filter_entity_id={entity_id}`) to query state changes from test-start to assertion-failure.

**Alternatives considered:**

- **WebSocket `subscribe_events`**: Requires persistent connection (current code opens/closes per-call), adds complexity for connection management and event buffering.
- **Polling observation**: Only captures what the assertion loop observed, misses setup-phase changes.

**Rationale:** History API is simple (single REST call), requires no new infrastructure, and captures all transitions including setup-phase changes.
Requires `recorder` integration to be enabled (default in HA).

### Always-on diagnostics

Automatically capture and append diagnostics to every `AssertionError` from `assert_entity_state` timeout failures.

**Alternatives considered:**

- **Opt-in** (parameter/fixture/config): Keeps fast path clean but requires test authors to remember to enable it.
  Failing tests are already a slow path, so the latency is acceptable.

**Rationale:** Diagnostics are almost always useful when an assertion fails.
The latency of a History API call (~100ms) is negligible compared to the 5s timeout.

### No causation tracking

Capture state/attribute transitions only. Do not attempt to determine what triggered each change (e.g. which automation fired, which service was called).

**Rationale:** HA's `state_changed` events don't carry causation info.
Determining triggers requires correlating `call_service`, `automation_triggered`, and other events by timestamp — a fragile, complex feature that deserves separate design if needed.
State change history alone is already a massive improvement.

### Output format: Append to AssertionError

Format diagnostics as a compact summary appended to the assertion error message:

```text
Entity light.living_room did not reach expected conditions within 5s.
state did not match 'on' (current: 'off')

State history (test-start → failure):
  +2.3s (14:23:01) → [created] off (brightness: 0)
  +5.1s (14:23:04) → on (brightness: 0→255, color_temp: 4000 (new))
  +7.2s (14:23:06) → on (unchanged) (brightness: 255→128)
```

**Alternatives considered:**

- **Separate log output**: Keeps assertion message clean but easy to miss in CI logs.
- **Both (summary in error, full in log)**: More complex, unclear where to draw the line.

**Rationale:** Appending ensures visibility. Compact format (last 10 transitions, delta-only for attributes) keeps the message readable.

### Time window: Test-start → assertion-failure

Capture the test start time via `pytest_runtest_setup` hook. Query History API from test-start to assertion-failure.

**Rationale:** Setup phase is often where bugs occur (e.g. automation fired unexpectedly during state injection). Capturing from test-start provides full context.

### Single entity

Query history only for the entity being asserted.

**Alternatives considered:**

- **All entities**: More data but noisy.
- **Configurable**: Adds API complexity.

**Rationale:** The assertion is about one entity. If broader diagnostics are needed, users can query the History API manually.

### Graceful degradation

If the History API call fails (e.g. recorder disabled, network error), append a note: `(History API unavailable: <error>)`. Test still fails with the original assertion.

**Rationale:** Diagnostics are supplementary. The primary failure is the assertion; if diagnostics are unavailable, the test should still fail clearly.

## Consequences

- **Positive:**
  - Test authors immediately see state transitions when assertions fail
  - Intermittent failures become diagnosable (can see if state oscillated)
  - Setup-phase bugs visible (e.g. automation fired before expected)
  - No API changes required (diagnostics are automatic)

- **Negative:**
  - Requires `recorder` integration (enabled by default, but can be disabled)
  - Adds ~100ms latency to assertion failures (acceptable for failing tests)
  - AssertionError messages become longer (mitigated by truncation)

- **Neutral:**
  - Does not capture causation (intentionally deferred/excluded)
  - Only captures state changes, not config changes (e.g. area/label updates via `given_entity_has`)
