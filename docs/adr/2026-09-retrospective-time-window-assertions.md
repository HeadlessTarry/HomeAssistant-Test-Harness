# Retrospective time-window assertions for entity state history

> **Status:** Active
> **Issue:** [#192 — Add retrospective time-window assertions for entity state history](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/192)
> **Date:** 2026-09

## Context

When automations have random delays or unpredictable timing, tests struggle to verify
that an entity entered a specific state during a time window. The current
`assert_entity_state` polls the entity's *current* state, but if the entity transitions
to the expected state and then back again before the assertion runs, the test fails even
though the automation worked correctly.

For example, a light that turns on at an unpredictable time within a 15-minute window
(due to random delays) and then turns off after a timer expires. The test can't reliably
assert the light is "on" at a specific moment because the assertion might run after the
timer has already turned it off.

## Decision

### New method: `assert_entity_was_in_state`

Add a new public method to the `HomeAssistant` client that queries the History API to verify an entity was in a specific state during a time window.

**Signature:**

```python
def assert_entity_was_in_state(
    self,
    entity_id: str,
    expected_state: Union[str, Callable[[str], bool], None] = None,
    between: tuple[datetime.time, datetime.time] = None,
    expected_attributes: Optional[dict[str, Any]] = None,
    require_full_duration: bool = False,
) -> list[dict[str, Any]]:
```

**Rationale:** A separate method makes test intent clear (retrospective vs. polling) and avoids overloading `assert_entity_state` with conflicting semantics.

### Two modes: transition vs. full-duration

Support two assertion modes via a `require_full_duration` flag:

- **Transition mode** (default): Asserts the entity entered the expected state at some point during the window.
- **Full-duration mode** (`require_full_duration=True`): Asserts the entity remained in the expected state throughout the entire window.

**Alternatives considered:**

- **Separate methods** (`assert_entity_transitioned_to_state` and
  `assert_entity_remained_in_state`): More explicit but increases API surface.
  Rejected in favor of a single method with a flag, which is more compact while
  still being clear.

**Rationale:** Both modes share the same time-window resolution and history-querying logic. A flag keeps the API surface small while preserving clarity via the parameter name.

### Time window resolution: `datetime.time` pairs relative to fake clock

Accept `between` as a tuple of `datetime.time` objects (not `datetime.datetime`), resolved to UTC datetimes using the fake clock's date (or real UTC if no fake time is set).

**Alternatives considered:**

- **`datetime.datetime` pairs**: More explicit but verbose for the common case.
  Rejected because time-of-day pairs are more natural for most test scenarios,
  and the fake clock's date provides the missing context.

**Rationale:** Time-of-day pairs are more natural for test scenarios like "verify the light turned on between 20:15 and 20:30". The fake clock's date provides the missing date context automatically.

### Midnight crossing support

If `min_time > max_time`, assume `max_time` is on the next day (e.g., `between=(time(23, 0), time(1, 0))` spans from 23:00 to 01:00 the next day).

**Rationale:** Many automations span midnight (e.g., "turn on the light between 11 PM and 1 AM"). Supporting this natively avoids requiring test authors to manually construct multi-day windows.

### Return matching history entries

Return the list of history entry dicts that match the criteria, allowing follow-up assertions on specific attributes or timestamps.

**Alternatives considered:**

- **Return nothing (void)**: Simpler API but prevents follow-up assertions. Rejected because test authors often want to verify specific timestamps or attribute values.

**Rationale:** Returning the matching entries enables composability — test authors can perform additional assertions on the returned data without re-querying the History API.

### Failure messages include window-scoped history

On failure, include both the local time window and the UTC datetimes used, plus a snippet of the state change history within the window (not the full test history).

**Rationale:** Window-scoped history reduces noise compared to full test history, while still providing enough context to diagnose why the assertion failed.

### Edge cases

- **No history in window**: Fail with "no state changes recorded".
- **Entity not in history**: Fail with "entity not found in history for the given window".
- **Zero-width window** (`min_time == max_time`): Raise `ValueError` (invalid input).
- **Future window**: Fail naturally with "no history found" (the History API returns empty results for future windows).

**Rationale:** Each edge case has a distinct failure mode that helps test authors understand what went wrong.

## Consequences

- **Positive:**
  - Tests can verify state transitions during time windows with unpredictable timing
  - Clear separation between polling (current state) and retrospective (historical state) assertions
  - Composable API — returned history entries enable follow-up assertions
  - Supports common patterns like midnight-crossing windows

- **Negative:**
  - Adds a new public API method (hard to reverse once tests use it)
  - Requires `recorder` integration (enabled by default, but can be disabled)
  - Adds latency to tests that use retrospective assertions (History API query)

- **Neutral:**
  - Does not replace `assert_entity_state` — both methods have distinct use cases
  - Failure messages include UTC datetimes, which may be confusing for test authors unfamiliar with the fake clock's date
