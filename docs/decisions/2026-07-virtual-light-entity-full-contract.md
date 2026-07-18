# 2026-07-virtual-light-entity-full-contract

> **Status:** Active
> **Issue:** [#132 — light.turn_on with brightness_pct does not store brightness attribute](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/132)
> **Date:** 2026-07-18

## Context

The `VirtualLightEntity` only declared `ONOFF`/`BRIGHTNESS`/`COLOR_TEMP`
color modes based on initial attributes, and only handled `brightness` and
`color_temp_kelvin` in `async_turn_on`. HA's `filter_turn_on_params` strips
attributes not supported by the entity's declared `supported_color_modes`
before they reach `async_turn_on`, causing `brightness_pct`, all color
attributes (`hs_color`, `rgb_color`, etc.), effects, flash, and transition
to be silently dropped.

## Decision

Always declare broad color mode support
(`{COLOR_TEMP, HS, RGB, RGBW, RGBWW, XY}`) from creation. Handle all
`async_turn_on`/`async_turn_off` kwargs (brightness, all color modes,
effect, flash, transition). Declare all feature flags
(`TRANSITION | FLASH | EFFECT`). Track `color_mode` dynamically based on
the most recently set color attribute via kwargs passed to `async_turn_on`,
rather than accumulated state.

## Consequences

- The virtual entity always supports color, even when tests don't need it.
  This is more permissive than some real lights but acceptable for a test
  harness.
- HA's `state_attributes` automatically derives cross-format color
  conversions (e.g., setting `hs_color` exposes `rgb_color`, `xy_color`
  in state).
- `color_mode` is tracked per-call from kwargs, avoiding stale mode from
  previously-set attributes.
- REST API returns color tuples as JSON arrays (lists), so test assertions
  must use list comparisons.
