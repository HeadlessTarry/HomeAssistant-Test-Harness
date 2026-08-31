# 🂡 Fluent Builder API for Virtual Entity Setup

## 🂢 Status

Accepted

## 🂢 Context

Setting up virtual entities with specific attributes and area assignments was verbose, requiring two separate calls:

```python
home_assistant.given_an_entity(
    "binary_sensor.study_pir",
    "off",
    attributes={"device_class": "motion"},
)
home_assistant.given_entity_has("binary_sensor.study_pir", area="study")
```

This approach had several drawbacks:

- Two separate method calls for a single logical operation
- Easy to forget `device_class` or area assignment
- Less discoverable API for common setup patterns

## 🂢 Decision

Introduce a fluent builder API that reduces verbosity while remaining explicit:

```python
home_assistant.given_an_entity("binary_sensor.study_pir", "off") \
    .with_device_class("motion") \
    .in_area("study")
```

### 🂣 API Design

The `EntityBuilder` class provides chainable methods:

- `with_device_class(device_class: str)` — sets the `device_class` attribute
- `in_area(area: str)` — assigns area
- `with_labels(labels: list[str])` — assigns labels
- `with_attributes(attributes: dict[str, Any])` — sets custom attributes (successive calls merge)

All methods return `Self` for chaining and apply changes immediately via the underlying `HomeAssistant` client.

### 🂣 Breaking Changes

1. **`attributes` parameter removed from `given_an_entity()`** — use `.with_attributes()` instead
2. **`given_entity_has()` removed from public API** — use builder's `.in_area()` and `.with_labels()` instead

The method `_given_entity_has()` remains internally for rollback operations but is no longer part of the public API.

### 🂣 Implementation Details

- **Eager entity creation**: Entities are created immediately on `given_an_entity()` call, not deferred to the first builder method
- **Stateful builder**: The builder holds a local `_attributes` dict that accumulates attribute changes. It fetches current remote state on construction and merges local changes on top when applying
- **Rollback tracking**: Builder methods that modify area/labels trigger `_track_entity_config_for_rollback()` before the first change
- **Attribute merging**: Successive `with_attributes()` calls merge into the builder's internal dict, then apply via `set_state()` with remote state preservation

### 🂣 Private Client Methods

Three private methods support the builder:

- `_track_entity_config_for_rollback(entity_id)` — saves pre-test config for restoration
- `_set_entity_area(entity_id, area)` — assigns area, creating it if needed
- `_set_entity_labels(entity_id, labels)` — assigns labels, creating them if needed

## 🂢 Consequences

### 🂣 Positive

- **Reduced verbosity**: Single chain replaces two separate calls
- **Discoverability**: Builder methods are autocomplete-friendly
- **Explicit intent**: Each chain step is clear and self-documenting
- **Flexible composition**: Methods can be combined in any order

### 🂣 Negative

- **Breaking change**: Existing tests using `attributes=` parameter must be updated
- **Migration effort**: Downstream projects need to update their test code

### 🂣 Neutral

- **`_given_entity_has()` retained internally**: Allows rollback logic to reuse existing code paths
- **No validation in builder**: Delegates to client methods, keeping builder simple

## 🂢 Migration Guide

### 🂣 Before

```python
home_assistant.given_an_entity("sensor.temp", "21.5", attributes={"unit_of_measurement": "°C"})
home_assistant.given_entity_has("sensor.temp", area="study")
```

### 🂣 After

```python
home_assistant.given_an_entity("sensor.temp", "21.5") \
    .with_attributes({"unit_of_measurement": "°C"}) \
    .in_area("study")
```

### 🂣 Before (with device_class and labels)

```python
home_assistant.given_an_entity("binary_sensor.motion", "off", attributes={"device_class": "motion"})
home_assistant.given_entity_has("binary_sensor.motion", area="study", labels=["security"])
```

### 🂣 After (with device_class and labels)

```python
home_assistant.given_an_entity("binary_sensor.motion", "off") \
    .with_device_class("motion") \
    .in_area("study") \
    .with_labels(["security"])
```
