# 2026-06-media-player-and-select-domains

> **Status:** Active
> **Issue:** [#109 — Support media_player and select domains in given_an_entity()](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/109)
> **Date:** 2026-06-11

## Context

The `given_an_entity()` method only supported four domains
(`sensor`, `binary_sensor`, `switch`, `light`), preventing creation of
entity-registered `media_player` and `select` instances. Tests that
referenced these domains (e.g., template sensors checking a TV's state)
had to use `set_state()` for unregistered state injection, which causes
`has_value()` in templates to return `false` and availability checks to
fail.

## Decision

Add `media_player` and `select` to `SUPPORTED_DOMAINS` following the
existing entity pattern: each new domain gets a `Virtual*Entity` class in
`entity.py`, a platform file, an entry in `SUPPORTED_DOMAINS`, and a
branch in `_create_virtual_entity()`. No new parameters or API surface
changes on `given_an_entity()`.

- `VirtualMediaPlayerEntity(MediaPlayerEntity)`: Supports
  `turn_on`→`"idle"`, `turn_off`→`"off"`, arbitrary state via
  `set_virtual_state()`, and passthrough attributes. Known limitations
  documented: no play/pause, volume, mute, source, or media metadata
  support.

- `VirtualSelectEntity(SelectEntity)`: Supports `options` list via
  attributes, `current_option` property, `async_select_option()` with
  validation, and `set_virtual_state()` that updates the options list.
  Filters `options` from `extra_state_attributes` (same pattern as
  `VirtualLightEntity` filtering `brightness`/`color_temp_kelvin`).

## Consequences

- Template sensors that depend on `media_player` or `select` entities
  can now be properly tested with registered entities.
- `media_player` entities support `turn_on`/`turn_off` actions via
  `call_action()`, making them compatible with
  `TestCallHomeAssitantActions`.
- `select` entities use `select_option` instead of `turn_on`/`turn_off`,
  so they are not in the turn-on/turn-off test class.
- `VirtualMediaPlayerEntity` has no `supported_features` bitmask — HA
  will show a minimal media player card. This can be extended later.
- The `input_boolean` domain remains in the module docstring but not in
  `SUPPORTED_DOMAINS` (pre-existing inconsistency preserved, not
  widened).
