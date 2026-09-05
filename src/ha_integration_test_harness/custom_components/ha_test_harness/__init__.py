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
  ha_test_harness/time/set          - Set absolute time (computes offset from real time).
  ha_test_harness/time/advance      - Advance time by a relative offset.
  ha_test_harness/time/get          - Get current fake time.
"""

from __future__ import annotations

import asyncio
import functools
import heapq
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

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

# Captured before time.time is patched, so the offset has a real base.
# This is the unpatched stdlib clock, used to compute the delta between real and fake time.
_real_time: Callable[[], float] = time.time

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeOffset:
    """The offset between real and fake time, as both a timedelta and seconds.

    Frozen, and replaced wholesale rather than updated in place. Handlers routinely
    read the offset, change it, then use the earlier value to work out how far time
    moved; if the offset were mutable that earlier read would see the new value and the
    difference would come out as zero. Immutability makes holding a reference safe, so
    that mistake cannot be made.

    Carrying the seconds view alongside the timedelta means the patched clock, which
    runs on every time.time() call in the process, does not reconstruct one per call.
    """

    delta: timedelta = timedelta(0)
    seconds: float = 0.0

    @classmethod
    def of(cls, delta: timedelta) -> TimeOffset:
        """Build an offset from a timedelta, deriving the seconds view."""
        return cls(delta, delta.total_seconds())


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
        "time_offset": TimeOffset(),  # offset applied to all HA time functions
    }

    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(discovery.async_load_platform(hass, domain, DOMAIN, {"domain": domain}, config))

    _apply_template_monkey_patch(hass)
    _apply_time_monkey_patch(hass)
    _apply_sun_monkey_patch(hass)

    websocket_api.async_register_command(hass, ws_create_entity)
    websocket_api.async_register_command(hass, ws_set_entity_state)
    websocket_api.async_register_command(hass, ws_delete_entity)
    websocket_api.async_register_command(hass, ws_freeze_template_entity)
    websocket_api.async_register_command(hass, ws_unfreeze_template_entity)
    websocket_api.async_register_command(hass, ws_time_set)
    websocket_api.async_register_command(hass, ws_time_advance)
    websocket_api.async_register_command(hass, ws_time_get)

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


def _apply_sun_monkey_patch(hass: HomeAssistant) -> None:
    """Monkey-patch the Sun entity's self-update callbacks to support freezing.

    When sun.sun is in the frozen_entities set, the patched methods skip the
    solar position recalculation entirely, preventing the Sun entity from
    overwriting any state override set via set_state().

    The Sun entity is a direct Entity subclass (not a TemplateEntity), so the
    template freeze mechanism does not protect it. It has two scheduled callbacks:
    - update_sun_position: recalculates elevation/azimuth every ~30s (day/twilight)
      or ~5min (night)
    - update_events: recalculates solar event times at each solar event

    Both are suppressed when sun.sun is frozen. Additionally, async_write_ha_state
    is patched on the Entity base class to prevent any state writes from the Sun
    entity while frozen (checking entity_id to only affect sun.sun).
    """
    try:
        from homeassistant.components.sun import Sun
        from homeassistant.helpers.entity import Entity
    except ImportError:
        _LOGGER.warning("[ha_test_harness] Could not import Sun/Entity; sun freeze not available")
        return

    original_update_sun_position = Sun.update_sun_position
    original_update_events = Sun.update_events
    original_async_write_ha_state = Entity.async_write_ha_state

    @callback
    def _patched_update_sun_position(self: Sun, now: Any = None) -> None:
        if "sun.sun" in hass.data[DOMAIN]["frozen_entities"]:
            return
        original_update_sun_position(self, now)

    @callback
    def _patched_update_events(self: Sun, now: Any = None) -> None:
        if "sun.sun" in hass.data[DOMAIN]["frozen_entities"]:
            return
        original_update_events(self, now)

    def _patched_async_write_ha_state(self: Entity, *args: Any, **kwargs: Any) -> None:
        if self.entity_id == "sun.sun" and "sun.sun" in hass.data[DOMAIN]["frozen_entities"]:
            return
        original_async_write_ha_state(self, *args, **kwargs)

    Sun.update_sun_position = _patched_update_sun_position  # type: ignore[method-assign]
    Sun.update_events = _patched_update_events  # type: ignore[method-assign]
    Entity.async_write_ha_state = _patched_async_write_ha_state  # type: ignore[method-assign,misc]
    _LOGGER.info("[ha_test_harness] Monkey-patched Sun callbacks for sun freeze support")


def _get_time_offset(hass: HomeAssistant) -> timedelta:
    """Get the current time offset."""
    current: TimeOffset = hass.data[DOMAIN]["time_offset"]
    return current.delta


def _set_time_offset(hass: HomeAssistant, offset: timedelta) -> None:
    """Replace the time offset in hass.data.

    Replaces rather than updates, so that any TimeOffset already handed out keeps the
    value it had when it was read.
    """
    hass.data[DOMAIN]["time_offset"] = TimeOffset.of(offset)


def _apply_time_monkey_patch(hass: HomeAssistant) -> None:
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

    The offset is stored in hass.data[DOMAIN]["time_offset"] and updated via the
    time/set and time/advance WebSocket commands.
    """
    from homeassistant.helpers import entity as entity_helpers
    from homeassistant.helpers import event as event_helpers

    real_time = _real_time
    # Capture the integration's own data dict, not the TimeOffset inside it: the offset
    # is replaced on every time change, so a captured TimeOffset would go stale. The
    # dict itself is created once in async_setup and never reassigned.
    domain_data: dict[str, Any] = hass.data[DOMAIN]

    def _fake_time() -> float:
        offset: TimeOffset = domain_data["time_offset"]
        return real_time() + offset.seconds

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

    _LOGGER.info("[ha_test_harness] Monkey-patched HA time functions for time control")


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
        vol.Required("type"): "ha_test_harness/template/freeze",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_freeze_template_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/template/freeze WebSocket command.

    Adds the entity to the frozen set, preventing TemplateEntity._handle_results
    from overwriting the state on template re-evaluation. Idempotent.
    """
    entity_id: str = msg["entity_id"]
    hass.data[DOMAIN]["frozen_entities"].add(entity_id)
    connection.send_result(msg["id"], {"entity_id": entity_id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/template/unfreeze",
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def ws_unfreeze_template_entity(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/template/unfreeze WebSocket command.

    Removes the entity from the frozen set, restoring normal template re-evaluation.
    Idempotent.
    """
    entity_id: str = msg["entity_id"]
    hass.data[DOMAIN]["frozen_entities"].discard(entity_id)
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

    Sets the fake time to an absolute ISO 8601 timestamp. Computes the offset
    from real time and stores it in hass.data[DOMAIN]["time_offset"]. Fires any
    scheduled timers that fall within the advanced time window.
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

    previous_offset = _get_time_offset(hass)
    offset = target_dt - datetime.fromtimestamp(_real_time(), timezone.utc)
    _set_time_offset(hass, offset)

    _LOGGER.info("[ha_test_harness] Time set to %s (offset: %s)", target_dt.isoformat(), offset)

    _advance_scheduled_timers(hass, (offset - previous_offset).total_seconds())
    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"timestamp": target_dt.isoformat(), "offset_seconds": offset.total_seconds()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/advance",
        vol.Required("seconds"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_time_advance(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/advance WebSocket command.

    Advances the fake time by the specified number of seconds (relative offset).
    Adds to the existing offset in hass.data[DOMAIN]["time_offset"]. Fires any
    scheduled timers that fall within the advanced time window.
    """
    seconds: float = msg["seconds"]
    delta = timedelta(seconds=seconds)

    current_offset = _get_time_offset(hass)
    new_offset = current_offset + delta
    _set_time_offset(hass, new_offset)
    new_time = datetime.fromtimestamp(_real_time(), timezone.utc) + new_offset

    _LOGGER.info("[ha_test_harness] Time advanced by %s seconds to %s", seconds, new_time.isoformat())

    _advance_scheduled_timers(hass, seconds)
    await _settle_after_time_change(hass)

    connection.send_result(msg["id"], {"timestamp": new_time.isoformat(), "offset_seconds": new_offset.total_seconds()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/get",
    }
)
@websocket_api.async_response
async def ws_time_get(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/get WebSocket command.

    Returns the current fake time as an ISO 8601 timestamp and the current offset.
    """
    offset = _get_time_offset(hass)
    fake_time = datetime.fromtimestamp(_real_time(), timezone.utc) + offset

    connection.send_result(
        msg["id"],
        {
            "timestamp": fake_time.isoformat(),
            "offset_seconds": offset.total_seconds(),
        },
    )
