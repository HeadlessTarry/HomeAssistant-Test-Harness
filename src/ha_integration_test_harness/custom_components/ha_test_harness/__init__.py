"""HA Test Harness custom integration.

Provides WebSocket commands for dynamically creating, updating, and deleting virtual
entities during integration tests. Entities are fully registered in the HA Entity
Registry (they have unique_ids), so they support area and label assignment via the
standard entity registry API.

Supported domains: sensor, binary_sensor, input_boolean, switch, light, media_player, select.

WebSocket commands exposed:
  ha_test_harness/entity/create     - Create a new virtual entity.
  ha_test_harness/entity/set_state  - Update state/attributes of an existing entity.
  ha_test_harness/entity/delete     - Remove an entity from HA entirely.
  ha_test_harness/template/freeze   - Freeze a template entity to prevent re-evaluation.
  ha_test_harness/template/unfreeze - Unfreeze a template entity to restore re-evaluation.
  ha_test_harness/time/set          - Set frozen time to an absolute timestamp.
  ha_test_harness/time/advance      - Advance frozen time by a relative offset.
  ha_test_harness/time/get          - Get current frozen time.
"""

from __future__ import annotations

import asyncio
import functools
import heapq
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import hass_wrapper
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.helpers import discovery
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .entity import (
    VirtualBinarySensorEntity,
    VirtualLightEntity,
    VirtualMediaPlayerEntity,
    VirtualSelectEntity,
    VirtualSensorEntity,
    VirtualToggleEntity,
)

DOMAIN = "ha_test_harness"
SUPPORTED_DOMAINS = ["sensor", "binary_sensor", "switch", "light", "media_player", "select"]
_PLATFORM_READY_TIMEOUT = 30  # seconds to wait for a platform callback to be registered
_SETTLE_TIMEOUT = 2  # seconds to let a time change take effect before replying
_SUN_ENTITY_ID = "sun.sun"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HA Test Harness integration.

    Initialises the in-memory entity store, loads a virtual-entity platform for each
    supported HA domain, and registers the three WebSocket command handlers.

    Args:
        hass: The Home Assistant instance.
        config: The full HA configuration dict (unused beyond being passed to platforms).

    Returns:
        True — setup always succeeds; individual platform failures are logged but do not
        prevent the integration from loading.
    """
    platform_ready_events: dict[str, asyncio.Event] = {domain: asyncio.Event() for domain in SUPPORTED_DOMAINS}
    hass.data[DOMAIN] = {
        "entities": {},  # entity_id -> VirtualEntity instance
        "add_callbacks": {},  # domain -> async_add_entities callback
        "platform_ready": platform_ready_events,
        "frozen_entities": set(),  # entity_ids of frozen template entities
        "sun_override": None,  # None = no override; dict = active sun override
    }

    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(discovery.async_load_platform(hass, domain, DOMAIN, {"domain": domain}, config))

    _apply_template_monkey_patch(hass)
    _apply_time_monkey_patch()
    _apply_sun_monkey_patch(hass)
    _apply_sun_helper_patches(hass)

    websocket_api.async_register_command(hass, ws_create_entity)
    websocket_api.async_register_command(hass, ws_set_entity_state)
    websocket_api.async_register_command(hass, ws_delete_entity)
    websocket_api.async_register_command(hass, ws_freeze_entity)
    websocket_api.async_register_command(hass, ws_unfreeze_entity)
    websocket_api.async_register_command(hass, ws_time_set)
    websocket_api.async_register_command(hass, ws_time_advance)
    websocket_api.async_register_command(hass, ws_time_get)
    websocket_api.async_register_command(hass, ws_sun_override)
    websocket_api.async_register_command(hass, ws_sun_restore)

    hass.services.async_register(
        "ai_task",
        "generate_data",
        async_service_generate_data,
        schema=vol.Schema({}, extra=vol.ALLOW_EXTRA),
        supports_response=SupportsResponse.ONLY,
    )

    _LOGGER.info("[ha_test_harness] Integration loaded")
    return True


def async_service_generate_data(call: ServiceCall) -> ServiceResponse:
    """Handle ai_task.generate_data service calls.

    Returns a fixed mock response to allow automations that use ai_task.generate_data
    to complete without error during integration tests.

    Args:
        call: The service call object containing task_name, instructions, and optional parameters.

    Returns:
        A dictionary with conversation_id (UUID) and data (fixed mock response).
    """
    _LOGGER.info("[ha_test_harness] ai_task.generate_data called with data: %s", call.data)
    return {
        "conversation_id": str(uuid.uuid4()),
        "data": "Mock AI response",
    }


def _apply_template_monkey_patch(hass: HomeAssistant) -> None:
    """Monkey-patch TemplateEntity._handle_results to support freezing template entities.

    When an entity_id is in the frozen_entities set, the patched method skips the
    template re-evaluation entirely, preventing the template from overwriting any
    state override set via set_state().
    """
    original_handle_results = TemplateEntity._handle_results

    @callback
    def _patched_handle_results(
        self: TemplateEntity,
        event: Any,
        updates: list[Any],
    ) -> None:
        entity_id = self.entity_id
        if entity_id in hass.data[DOMAIN]["frozen_entities"]:
            return
        original_handle_results(self, event, updates)

    TemplateEntity._handle_results = _patched_handle_results  # type: ignore[method-assign]
    _LOGGER.info("[ha_test_harness] Monkey-patched TemplateEntity._handle_results for template freeze support")


def _get_sun_entity_instance(hass: HomeAssistant) -> Any:
    """Find the Sun entity instance via config entries.

    The Sun entity is stored as config_entry.runtime_data, not in hass.data["sun"].
    Returns None if not found.
    """
    try:
        for entry in hass.config_entries.async_entries("sun"):
            runtime_data = getattr(entry, "runtime_data", None)
            if runtime_data is not None:
                return runtime_data
    except Exception:  # noqa: BLE001
        pass
    return None


def _apply_sun_monkey_patch(hass: HomeAssistant) -> None:
    """Monkey-patch the Sun entity's state write method to support freezing.

    When sun.sun is in the frozen_entities set, the patched method skips the state
    write entirely, preventing the Sun entity from overwriting any state override
    set via set_state().

    The Sun entity is a direct Entity subclass (not a TemplateEntity), so the
    template freeze mechanism does not protect it. It has two scheduled callbacks:
    - update_sun_position: recalculates elevation/azimuth every ~30s (day/twilight)
      or ~5min (night)
    - update_events: recalculates solar event times at each solar event

    These callbacks are cancelled when sun.sun is frozen (via the freeze handler),
    and restored when unfrozen. The monkey-patch serves as a safety net to catch
    any writes that slip through.

    We patch _async_write_ha_state (not async_write_ha_state) because the latter
    is marked @final and just delegates to _async_write_ha_state after validation.
    All actual state writes funnel through _async_write_ha_state.
    """
    try:
        from homeassistant.components.sun import Sun
    except ImportError:
        _LOGGER.warning("[ha_test_harness] Could not import Sun; sun freeze not available")
        return

    original_async_write_ha_state = Sun._async_write_ha_state

    def _patched_async_write_ha_state(self: Sun, *args: Any, **kwargs: Any) -> None:
        frozen_set = hass.data[DOMAIN]["frozen_entities"]
        if _SUN_ENTITY_ID in frozen_set:
            return
        original_async_write_ha_state(self, *args, **kwargs)

    Sun._async_write_ha_state = _patched_async_write_ha_state  # type: ignore[method-assign,assignment]
    _LOGGER.info("[ha_test_harness] Monkey-patched Sun._async_write_ha_state for sun freeze support")


def _freeze_sun(hass: HomeAssistant) -> None:
    """Cancel the Sun entity's pending scheduled callbacks.

    Cancels update_sun_position and update_events listeners to prevent them from
    mutating instance attributes and writing state while sun.sun is frozen.
    """
    sun_entity = _get_sun_entity_instance(hass)
    if sun_entity is None:
        return
    if getattr(sun_entity, "_update_sun_position_listener", None):
        sun_entity._update_sun_position_listener()
        sun_entity._update_sun_position_listener = None
    if getattr(sun_entity, "_update_events_listener", None):
        sun_entity._update_events_listener()
        sun_entity._update_events_listener = None
    _LOGGER.info("[ha_test_harness] Cancelled Sun entity listeners for freeze")


def _unfreeze_sun(hass: HomeAssistant) -> None:
    """Restore the Sun entity's scheduled callbacks.

    Triggers update_location(initial=True) to recalculate solar position from the
    current fake time and re-schedule the Sun entity's timers.
    """
    sun_entity = _get_sun_entity_instance(hass)
    if sun_entity is None:
        return
    # Force a full recalculation by calling update_location with initial=True
    # This recalculates all sun attributes including elevation, azimuth, next_rising, next_setting
    sun_entity.update_location(initial=True)
    # Also force an async_update to ensure the state is written
    hass.async_create_task(sun_entity.async_update_ha_state(force_refresh=True))
    _LOGGER.info("[ha_test_harness] Restored Sun entity listeners after unfreeze")


# Store original sun helper functions before patching
_original_sun_helpers: dict[str, Any] = {}


def _compute_overridden_astral_event(override: dict[str, Any], event: str, utc_point_in_time: datetime) -> datetime:
    """Compute a fake astral event time based on the active sun override."""
    is_up = bool(override.get("is_up", True))
    is_future = (event == "sunset") == is_up
    return utc_point_in_time + timedelta(hours=6) if is_future else utc_point_in_time - timedelta(hours=6)


def _apply_sun_helper_patches(hass: HomeAssistant) -> None:
    """Monkey-patch sun helper functions to support sun condition overrides.

    Patches homeassistant.helpers.sun.is_up and get_astral_event_next to check
    for an active sun override before computing astronomical values. Also patches
    astral.sun.elevation in the sun condition module.

    The override is stored in hass.data[DOMAIN]["sun_override"] and can be set
    via the ws_sun_override WebSocket command.
    """
    try:
        import astral.sun
        from homeassistant.components.sun import condition as sun_condition
        from homeassistant.helpers import sun as sun_helpers
    except ImportError:
        _LOGGER.warning("[ha_test_harness] Could not import sun helpers; sun override not available")
        return

    # Store originals
    _original_sun_helpers["is_up"] = sun_helpers.is_up
    _original_sun_helpers["get_astral_event_next"] = sun_helpers.get_astral_event_next
    _original_sun_helpers["astral_sun_elevation"] = astral.sun.elevation

    domain_data: dict[str, Any] = hass.data[DOMAIN]

    def _patched_is_up(hass_obj: HomeAssistant, utc_point_in_time: datetime | None = None) -> bool:
        """Check if sun is up, respecting override if active."""
        override = domain_data.get("sun_override")
        if override is not None:
            # Override is active - return the overridden value
            return bool(override.get("is_up", True))
        # No override - use original function
        return bool(_original_sun_helpers["is_up"](hass_obj, utc_point_in_time))

    def _patched_get_astral_event_next(
        hass_obj: HomeAssistant,
        event: str,
        utc_point_in_time: datetime | None = None,
        offset: timedelta | None = None,
    ) -> datetime:
        """Get next astral event, respecting override if active."""
        override = domain_data.get("sun_override")
        if override is not None:
            if utc_point_in_time is None:
                utc_point_in_time = dt_util.utcnow()
            return _compute_overridden_astral_event(override, event, utc_point_in_time)
        from typing import cast

        return cast(datetime, _original_sun_helpers["get_astral_event_next"](hass_obj, event, utc_point_in_time, offset))

    def _patched_astral_sun_elevation(observer: Any, dt: datetime) -> float:
        """Get sun elevation, respecting override if active."""
        override = domain_data.get("sun_override")
        if override is not None and "elevation" in override:
            return float(override["elevation"])
        # No override - use original function
        return float(_original_sun_helpers["astral_sun_elevation"](observer, dt))

    # Apply patches
    sun_helpers.is_up = _patched_is_up  # type: ignore[assignment]
    sun_helpers.get_astral_event_next = _patched_get_astral_event_next  # type: ignore[assignment]
    astral.sun.elevation = _patched_astral_sun_elevation

    # Also patch the imports in sun.condition module
    if hasattr(sun_condition, "is_up"):
        sun_condition.is_up = _patched_is_up  # type: ignore[assignment]
    if hasattr(sun_condition, "get_astral_event_next"):
        sun_condition.get_astral_event_next = _patched_get_astral_event_next

    _LOGGER.info("[ha_test_harness] Monkey-patched sun helper functions for sun override support")


def _apply_time_monkey_patch() -> None:
    """Move every wall clock Home Assistant can read onto the fake clock at once.

    Home Assistant reads the wall clock through several unrelated routes, and they must
    agree. Where they disagree, HA compares a fake timestamp against a real one and
    draws nonsense conclusions - a state that changed "3 hours ago", a rate limit that
    expires in 13 hours, an automation that fires the instant time moves.

    The routes are:
      - time.time(), read directly by homeassistant.core (state and event timestamps),
        homeassistant.helpers.event and homeassistant.helpers.ratelimit
      - homeassistant.helpers.entity.timer, a module-level alias of time.time bound at
        import time, which stamps every entity state write
      - homeassistant.util.dt.utcnow / now, the sanctioned helpers, which call
        datetime.now() rather than time.time()
      - homeassistant.helpers.event.time_tracker_utcnow / time_tracker_timestamp

    Patching time.time covers the first group process-wide, including modules we have
    not had to name. Aliases bound at import time are re-pointed individually, and the
    datetime-based helpers are replaced separately because datetime.now() is
    implemented in C and does not call time.time().

    Deliberately NOT patched: time.monotonic. asyncio and aiohttp measure timeouts and
    schedule callbacks against the monotonic clock, so leaving it real keeps the event
    loop and the connection carrying these commands working normally while wall-clock
    time moves.

    Time is frozen at the value stored in hass_wrapper._frozen_time_value and updated
    via the time/set and time/advance WebSocket commands.
    """
    from homeassistant.helpers import entity as entity_helpers
    from homeassistant.helpers import event as event_helpers

    def _fake_time() -> float:
        return float(hass_wrapper.get_fake_time())

    def _fake_utcnow() -> datetime:
        return datetime.fromtimestamp(_fake_time(), timezone.utc)

    def _fake_now(time_zone: Any = None) -> datetime:
        import homeassistant.util.dt as dt_util_module

        if time_zone is None:
            time_zone = dt_util_module.DEFAULT_TIME_ZONE
        return _fake_utcnow().astimezone(time_zone)

    time.time = _fake_time
    entity_helpers.timer = _fake_time
    dt_util.utcnow = _fake_utcnow
    dt_util.now = _fake_now
    event_helpers.time_tracker_utcnow = _fake_utcnow
    event_helpers.time_tracker_timestamp = _fake_time

    _LOGGER.info("[ha_test_harness] Monkey-patched HA time functions for frozen time control")


def _is_home_assistant_timer(handle: asyncio.TimerHandle) -> bool:
    """Return True if the handle belongs to Home Assistant's own scheduling.

    The fake clock governs Home Assistant's behaviour, not the transport carrying the
    test's commands. The event loop also holds timers for aiohttp (including the
    heartbeat and timeout of the very WebSocket connection this command arrived on),
    asyncio, zeroconf and bluetooth. Moving those deadlines makes aiohttp conclude the
    connection has died mid-request, which surfaces to the test as a connection
    timeout, so they are left on the real clock - which is also the clock they measure
    against, since asyncio schedules on time.monotonic.

    functools.partial is unwrapped before reading __module__, because a partial reports
    its own module rather than the wrapped function's and would be misclassified as
    non-HA. No scheduled handle in the HA version this was written against actually
    wraps its callback that way, so this is a guard against HA changing rather than a
    fix for observed behaviour.
    """
    callback = handle._callback  # type: ignore[attr-defined]
    while isinstance(callback, functools.partial):
        callback = callback.func
    module = getattr(callback, "__module__", None)
    return isinstance(module, str) and (module == "homeassistant" or module.startswith("homeassistant."))


def _advance_scheduled_timers(hass: HomeAssistant, delta_seconds: float) -> int:
    """Bring Home Assistant's pending timer deadlines forward onto the fake clock.

    Callbacks are scheduled with loop.call_at, which measures against the monotonic
    clock. The monotonic clock does not move when fake time does, so without this a
    ``delay: 00:30:00`` would wait thirty real minutes and a time trigger three fake
    hours away would never arrive.

    Because time.time() is patched, both ways HA schedules a callback express their
    deadline as a fake-time duration from the moment they were scheduled:

      - relative, e.g. async_call_later and script ``delay:``:
        ``call_at(loop.time() + duration)``
      - absolute, e.g. async_track_point_in_utc_time and HA timer entities:
        ``call_at(loop.time() + target_timestamp - time.time())``

    So subtracting the offset delta from every pending deadline is correct for both,
    and a callback becomes due exactly when that much fake time has elapsed. Once a
    deadline is in the past the event loop runs it itself, in order, with normal
    exception handling - no need to invoke callbacks by hand.

    Uses loop._scheduled, a CPython implementation detail (a heapq of TimerHandle),
    guarded by a runtime attribute check rather than an HA version check so that it
    degrades to a warning rather than crashing if it ever disappears. The heap is
    re-heapified because only a subset of handles is moved, which can reorder them.
    """
    loop = hass.loop
    if not hasattr(loop, "_scheduled"):
        _LOGGER.warning("[ha_test_harness] Event loop does not have _scheduled attribute; cannot advance timers")
        return 0
    if delta_seconds <= 0:
        return 0

    advanced = 0
    for handle in loop._scheduled:
        if not isinstance(handle, asyncio.TimerHandle) or handle.cancelled():
            continue
        if not _is_home_assistant_timer(handle):
            continue
        handle._when -= delta_seconds  # type: ignore[attr-defined]
        advanced += 1

    if advanced:
        heapq.heapify(loop._scheduled)

    return advanced


async def _settle_after_time_change(hass: HomeAssistant) -> None:
    """Let the effects of a time change land, without waiting on sleeping automations.

    hass.async_block_till_done() waits for every tracked task to finish. An automation
    part-way through a ``delay:`` step is such a task, and its delay can only elapse
    when fake time advances again - which cannot happen while this handler is still
    holding the connection that would deliver the next time command. Waiting
    unconditionally therefore deadlocks until the client's socket times out.

    Bounding the wait keeps the common case (let automations run to completion before
    replying) while returning promptly when something is deliberately asleep.
    Cancelling async_block_till_done only abandons its asyncio.wait; the tasks
    themselves are left running.
    """
    try:
        async with asyncio.timeout(_SETTLE_TIMEOUT):
            await hass.async_block_till_done()
    except TimeoutError:
        _LOGGER.debug("[ha_test_harness] Tasks still pending %ss after time change; replying anyway", _SETTLE_TIMEOUT)


def _create_virtual_entity(domain: str, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> Any:
    """Instantiate the correct VirtualEntity subclass for the given domain.

    Args:
        domain: HA domain ('sensor', 'binary_sensor', 'input_boolean', 'switch', 'light', 'media_player', 'select').
        unique_id: Unique ID string for the entity registry entry.
        entity_id: Desired entity ID (e.g. 'sensor.test_temp').
        state: Initial state string.
        attributes: Initial extra attributes dict.

    Returns:
        A VirtualEntity instance appropriate for the domain.

    Raises:
        ValueError: If the domain is not in SUPPORTED_DOMAINS.
    """
    if domain == "sensor":
        return VirtualSensorEntity(unique_id, entity_id, state, attributes)
    if domain == "binary_sensor":
        return VirtualBinarySensorEntity(unique_id, entity_id, state, attributes)
    if domain in ("switch", "input_boolean"):
        return VirtualToggleEntity(unique_id, entity_id, state, attributes)
    if domain == "light":
        return VirtualLightEntity(unique_id, entity_id, state, attributes)
    if domain == "media_player":
        return VirtualMediaPlayerEntity(unique_id, entity_id, state, attributes)
    if domain == "select":
        return VirtualSelectEntity(unique_id, entity_id, state, attributes)
    raise ValueError(f"Unsupported domain: {domain}")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/entity/create",
        vol.Required("entity_id"): str,
        vol.Required("state"): str,
        vol.Optional("attributes"): dict,
    }
)
@websocket_api.async_response
async def ws_create_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/entity/create WebSocket command.

    Creates a new virtual entity, registers it with the appropriate HA platform, and
    responds with the assigned entity_id and unique_id.  Returns an error if the
    entity_id is already managed by this integration, or if the domain is unsupported.
    """
    entity_id: str = msg["entity_id"]
    state: str = msg["state"]
    attributes: dict[str, Any] = msg.get("attributes") or {}

    parts = entity_id.split(".", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        connection.send_error(msg["id"], "invalid_format", f"Invalid entity_id format: {entity_id!r}")
        return

    domain = parts[0]
    if domain not in SUPPORTED_DOMAINS:
        connection.send_error(msg["id"], "unsupported_domain", f"Domain {domain!r} is not supported. Supported domains: {SUPPORTED_DOMAINS}")
        return

    if entity_id in hass.data[DOMAIN]["entities"]:
        connection.send_error(msg["id"], "already_exists", f"Entity {entity_id!r} already exists in ha_test_harness")
        return

    # Wait for the platform callback to become available (set during async_setup_platform).
    platform_event: asyncio.Event = hass.data[DOMAIN]["platform_ready"][domain]
    if not platform_event.is_set():
        try:
            await asyncio.wait_for(platform_event.wait(), timeout=_PLATFORM_READY_TIMEOUT)
        except asyncio.TimeoutError:
            connection.send_error(msg["id"], "platform_timeout", f"Platform {domain!r} not ready after {_PLATFORM_READY_TIMEOUT}s")
            return

    unique_id = f"ha_test_harness_{entity_id.replace('.', '_')}"
    entity = _create_virtual_entity(domain, unique_id, entity_id, state, attributes)

    hass.data[DOMAIN]["add_callbacks"][domain]([entity])
    # Yield once to allow the entity's async_write_ha_state() call to propagate through
    # the HA event loop without waiting for unrelated background tasks.  Using
    # async_block_till_done() here would drain ALL pending asyncio tasks — including
    # sleeping automation actions triggered by the new entity's state change — which
    # causes multi-second (or multi-minute) delays in heavy HA configurations.
    await asyncio.sleep(0)

    actual_entity_id: str = entity.entity_id
    if actual_entity_id != entity_id:
        # HA assigned a different entity_id (e.g. due to conflict).  Clean up and report.
        _LOGGER.error("[ha_test_harness] Requested entity_id %r but HA assigned %r — possible conflict", entity_id, actual_entity_id)
        try:
            await entity.async_remove(force_remove=True)
        except Exception:  # noqa: BLE001
            pass
        connection.send_error(msg["id"], "entity_id_conflict", f"Requested entity_id {entity_id!r} already taken; HA assigned {actual_entity_id!r}")
        return

    hass.data[DOMAIN]["entities"][entity_id] = entity
    connection.send_result(msg["id"], {"entity_id": entity_id, "unique_id": unique_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/entity/set_state",
        vol.Required("entity_id"): str,
        vol.Required("state"): str,
        vol.Optional("attributes"): dict,
    }
)
@websocket_api.async_response
async def ws_set_entity_state(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/entity/set_state WebSocket command.

    Updates the state (and optionally attributes) of an existing virtual entity.
    """
    entity_id: str = msg["entity_id"]
    state: str = msg["state"]
    attributes: dict[str, Any] | None = msg.get("attributes")

    entity = hass.data[DOMAIN]["entities"].get(entity_id)
    if entity is None:
        connection.send_error(msg["id"], "not_found", f"Entity {entity_id!r} not found in ha_test_harness")
        return

    entity.set_virtual_state(state, attributes)
    # Yield once — same rationale as ws_create_entity: avoid draining unrelated tasks.
    await asyncio.sleep(0)
    connection.send_result(msg["id"], {"entity_id": entity_id, "state": state})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/entity/delete",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/entity/delete WebSocket command.

    Removes the entity from the HA state machine, entity platform, and entity registry.
    Returns success even if the entity is not found (idempotent).
    """
    entity_id: str = msg["entity_id"]

    entity = hass.data[DOMAIN]["entities"].pop(entity_id, None)
    if entity is None:
        # Already gone — treat as success (idempotent cleanup).
        connection.send_result(msg["id"], {"entity_id": entity_id})
        return

    try:
        await entity.async_remove(force_remove=True)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("[ha_test_harness] Error removing entity %r from platform: %s", entity_id, exc)

    try:
        registry = er.async_get(hass)
        registry.async_remove(entity_id)
    except Exception as exc:  # noqa: BLE001
        _LOGGER.warning("[ha_test_harness] Error removing entity %r from registry: %s", entity_id, exc)

    connection.send_result(msg["id"], {"entity_id": entity_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/entity/freeze",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_freeze_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/entity/freeze WebSocket command.

    Adds the entity to the frozen set, preventing self-updating behavior from
    overwriting state overrides. Supported entities:
    - Template entities: TemplateEntity._handle_results skips re-evaluation
    - sun.sun: Sun._async_write_ha_state skips writes, and scheduled callbacks
      (update_sun_position, update_events) are cancelled

    Idempotent.
    """
    entity_id: str = msg["entity_id"]
    hass.data[DOMAIN]["frozen_entities"].add(entity_id)

    if entity_id == _SUN_ENTITY_ID:
        _freeze_sun(hass)

    connection.send_result(msg["id"], {"entity_id": entity_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/entity/unfreeze",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_unfreeze_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/entity/unfreeze WebSocket command.

    Removes the entity from the frozen set, restoring normal self-updating behavior.
    Idempotent.
    """
    entity_id: str = msg["entity_id"]
    hass.data[DOMAIN]["frozen_entities"].discard(entity_id)

    if entity_id == _SUN_ENTITY_ID:
        _unfreeze_sun(hass)

    connection.send_result(msg["id"], {"entity_id": entity_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/set",
        vol.Required("timestamp"): str,
    }
)
@websocket_api.async_response
async def ws_time_set(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/set WebSocket command.

    Sets the frozen time to an absolute ISO 8601 timestamp. Directly sets the frozen
    timestamp value in hass_wrapper. Fires any scheduled timers that fall within the
    advanced time window.
    """
    timestamp_str: str = msg["timestamp"]

    try:
        target_dt = datetime.fromisoformat(timestamp_str)
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        else:
            target_dt = target_dt.astimezone(timezone.utc)
    except (ValueError, AttributeError) as e:
        connection.send_error(msg["id"], "invalid_timestamp", f"Invalid ISO 8601 timestamp: {timestamp_str!r}: {e}")
        return

    previous_time = hass_wrapper.get_fake_time()
    target_timestamp = target_dt.timestamp()
    hass_wrapper.set_fake_time(target_timestamp)

    _LOGGER.info("[ha_test_harness] Time set to %s", target_dt.isoformat())

    delta_seconds = target_timestamp - previous_time
    _advance_scheduled_timers(hass, delta_seconds)
    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"timestamp": target_dt.isoformat(), "offset_seconds": 0.0})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/advance",
        vol.Required("seconds"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_time_advance(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/advance WebSocket command.

    Advances the frozen time by the specified number of seconds (relative offset).
    Adds to the existing frozen timestamp in hass_wrapper. Fires any scheduled timers
    that fall within the advanced time window.

    Uses chunked advancement to handle cascading timers: when automations trigger
    during settle and schedule new timers (e.g., delay actions), those timers need
    their deadlines moved forward too. By breaking large advances into smaller chunks,
    each chunk can advance and settle, allowing cascading timers to be picked up.
    """
    seconds: float = msg["seconds"]

    current_time = hass_wrapper.get_fake_time()
    new_time = current_time + seconds
    hass_wrapper.set_fake_time(new_time)
    new_dt = datetime.fromtimestamp(new_time, timezone.utc)

    _LOGGER.info("[ha_test_harness] Time advanced by %s seconds to %s", seconds, new_dt.isoformat())

    _advance_scheduled_timers(hass, seconds)
    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"timestamp": new_dt.isoformat(), "offset_seconds": 0.0})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/get",
    }
)
@websocket_api.async_response
async def ws_time_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/get WebSocket command.

    Returns the current frozen time as an ISO 8601 timestamp.
    """
    frozen_timestamp = hass_wrapper.get_fake_time()
    fake_time = datetime.fromtimestamp(frozen_timestamp, timezone.utc)

    connection.send_result(
        msg["id"],
        {
            "timestamp": fake_time.isoformat(),
            "offset_seconds": 0.0,
        },
    )


_STATE_TO_IS_UP = {"above_horizon": True, "below_horizon": False}
_STATE_TO_DEFAULT_ELEVATION = {"above_horizon": 15.0, "below_horizon": -5.0}


def _build_sun_override(state: str | None, elevation: float | None) -> tuple[dict[str, Any], str | None]:
    """Build sun override dict from state and elevation parameters."""
    override: dict[str, Any] = {}

    if state is not None:
        if state not in _STATE_TO_IS_UP:
            return {}, f"Invalid state: {state!r}. Must be 'above_horizon' or 'below_horizon'"
        override["is_up"] = _STATE_TO_IS_UP[state]

    if elevation is not None:
        override["elevation"] = elevation
        if "is_up" not in override:
            override["is_up"] = elevation > -0.833

    if state is not None and elevation is None:
        override["elevation"] = _STATE_TO_DEFAULT_ELEVATION[state]

    return override, None


def _build_sun_attrs(
    override: dict[str, Any],
    azimuth: float | None,
    additional_attrs: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build sun entity attributes from override dict."""
    is_up = override.get("is_up", True)
    now = dt_util.utcnow()
    past = (now - timedelta(hours=6)).isoformat()
    future = (now + timedelta(hours=6)).isoformat()

    sun_attrs: dict[str, Any] = {}
    if "elevation" in override:
        sun_attrs["elevation"] = override["elevation"]
    if azimuth is not None:
        sun_attrs["azimuth"] = azimuth
    else:
        sun_attrs["azimuth"] = 180.0 if is_up else 0.0
    sun_attrs["next_rising"] = past if is_up else future
    sun_attrs["next_setting"] = future if is_up else past

    if additional_attrs:
        sun_attrs.update(additional_attrs)

    return sun_attrs


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/sun/override",
        vol.Optional("state"): str,
        vol.Optional("elevation"): vol.Coerce(float),
        vol.Optional("azimuth"): vol.Coerce(float),
        vol.Optional("attributes"): dict,
    }
)
@websocket_api.async_response
async def ws_sun_override(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/sun/override WebSocket command.

    Overrides sun conditions to return the specified values. Patches is_up(),
    get_astral_event_next(), and astral.sun.elevation() to return overridden values.
    Also sets the sun.sun entity state and attributes.

    Args:
        state: "above_horizon" or "below_horizon" (optional)
        elevation: Sun elevation in degrees (optional)
        azimuth: Sun azimuth in degrees (optional)
        attributes: Additional attributes to set on sun.sun (optional)
    """
    state: str | None = msg.get("state")
    elevation: float | None = msg.get("elevation")
    azimuth: float | None = msg.get("azimuth")
    additional_attrs: dict[str, Any] | None = msg.get("attributes")

    override, error = _build_sun_override(state, elevation)
    if error is not None:
        connection.send_error(msg["id"], "invalid_state", error)
        return

    # Store override
    hass.data[DOMAIN]["sun_override"] = override

    # Freeze sun.sun to prevent it from overwriting our override
    hass.data[DOMAIN]["frozen_entities"].add(_SUN_ENTITY_ID)
    _freeze_sun(hass)

    # Set sun.sun entity state
    sun_state = "above_horizon" if override.get("is_up", True) else "below_horizon"
    sun_attrs = _build_sun_attrs(override, azimuth, additional_attrs)

    # Update sun.sun entity state via REST API
    hass.states.async_set(_SUN_ENTITY_ID, sun_state, sun_attrs)

    _LOGGER.info("[ha_test_harness] Sun override applied: %s", override)

    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"override": override, "state": sun_state})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/sun/restore",
    }
)
@websocket_api.async_response
async def ws_sun_restore(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/sun/restore WebSocket command.

    Clears the sun override and unfreezes sun.sun, allowing it to recalculate
    from the current fake time.
    """
    # Clear override FIRST so patched functions return real values
    hass.data[DOMAIN]["sun_override"] = None

    # Unfreeze sun.sun FIRST so state writes aren't blocked
    hass.data[DOMAIN]["frozen_entities"].discard(_SUN_ENTITY_ID)
    _unfreeze_sun(hass)

    # Get the sun entity and force a full recalculation
    sun_entity = _get_sun_entity_instance(hass)
    if sun_entity is not None:
        # update_location(initial=True) recalculates elevation, azimuth, next_rising, next_setting
        sun_entity.update_location(initial=True)
        # Force state write now that we're unfrozen
        sun_entity.async_write_ha_state()

    _LOGGER.info("[ha_test_harness] Sun override cleared, sun.sun recalculated from fake time")

    # Wait for the state to propagate
    await asyncio.sleep(0.5)
    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"restored": True})
