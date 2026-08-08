# 2026-07-media-player-service-call-mocking

> **Status:** Active
> **Issue:** [#121 — Support mocking media_player service calls](https://github.com/HeadlessTarry/HomeAssistant-Test-Harness/issues/121)
> **Date:** 2026-07-04

## Context

The test harness's `VirtualMediaPlayerEntity` only declared `TURN_ON | TURN_OFF` feature flags.
When automations called `media_player.play_media` or other service calls on test entities, HA
rejected them before they reached the entity — blocking integration tests for morning alarm
automations, mockupancy radio, and any automation that plays media.

## Decision

Expanded `VirtualMediaPlayerEntity` in `entity.py` to support 12 media player service calls:

- **8 playback transport:** `play_media`, `media_play`, `media_pause`, `media_stop`, `media_play_pause`, `media_next_track`, `media_previous_track`, `media_seek`
- **4 volume:** `volume_set`, `volume_up`, `volume_down`, `volume_mute`

Each service call maps to an async handler method on the entity that updates internal state and
calls `async_write_ha_state()`. Feature flags were expanded to match so HA dispatches the calls
correctly.

Key design choices:

- `play_media` auto-powers-on from `off` (transitions to `playing`)
- Transport controls are no-ops for invalid states (e.g., `media_play` when `off`)
- Volume actions work regardless of power state
- `set_virtual_state()` syncs known media/volume keys into dedicated backing fields for HA property consistency
- Volume clamping (0.0-1.0) is defensive — HA's service schema validates ranges at the API level

## Consequences

- Tests can now verify automations that play media using `call_action()` + `assert_entity_state()`
- `media_track` and `media_position` are exposed via `extra_state_attributes`
- `volume_level` and `is_volume_muted` are exposed via HA-standard properties
- Volume clamp tests were removed — HA prevents out-of-range values from reaching the entity
- `volume_level` is not visible in state attributes when entity is off
