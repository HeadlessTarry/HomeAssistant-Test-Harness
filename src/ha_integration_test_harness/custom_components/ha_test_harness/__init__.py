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
  ha_test_harness/time/set          - Set absolute fake time.
  ha_test_harness/time/advance      - Advance fake time by delta.
  ha_test_harness/time/get          - Get current fake time.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.helpers import discovery
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

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
        "time_offset": timedelta(),  # offset from real time for fake time
        "time_patchers": None,  # will hold the context manager for time patching
    }

    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(discovery.async_load_platform(hass, domain, DOMAIN, {"domain": domain}, config))

    _apply_template_monkey_patch(hass)
    _apply_time_tracker_patch(hass)

    websocket_api.async_register_command(hass, ws_create_entity)
    websocket_api.async_register_command(hass, ws_set_entity_state)
    websocket_api.async_register_command(hass, ws_delete_entity)
    websocket_api.async_register_command(hass, ws_freeze_template_entity)
    websocket_api.async_register_command(hass, ws_unfreeze_template_entity)
    websocket_api.async_register_command(hass, ws_set_time)
    websocket_api.async_register_command(hass, ws_advance_time)
    websocket_api.async_register_command(hass, ws_get_time)

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


def _apply_time_tracker_patch(hass: HomeAssistant) -> None:
    """Monkey-patch HA's time functions to support fake time.

    Patches:
    - homeassistant.helpers.event.time_tracker_utcnow
    - homeassistant.helpers.event.time_tracker_timestamp
    - homeassistant.util.dt.utcnow
    - homeassistant.util.dt.now
    to return time adjusted by the offset stored in hass.data[DOMAIN]["time_offset"].
    """
    from homeassistant.helpers import event as event_helper

    def _fake_utcnow() -> datetime:
        """Return fake UTC time (real time + offset)."""
        result: datetime = datetime.now(timezone.utc) + hass.data[DOMAIN]["time_offset"]
        return result

    def _fake_timestamp() -> float:
        """Return fake timestamp (real time + offset)."""
        result: float = time.time() + hass.data[DOMAIN]["time_offset"].total_seconds()
        return result

    def _fake_dt_utcnow() -> datetime:
        """Return fake UTC time for dt_util (real time + offset)."""
        result: datetime = datetime.now(timezone.utc) + hass.data[DOMAIN]["time_offset"]
        return result

    def _fake_dt_now(tz: Any = None) -> datetime:
        """Return fake local time for dt_util (real time + offset)."""
        import homeassistant.util.dt as dt_util_module

        if tz is None:
            tz = dt_util_module.DEFAULT_TIME_ZONE
        result: datetime = (datetime.now(timezone.utc) + hass.data[DOMAIN]["time_offset"]).astimezone(tz)
        return result

    event_helper.time_tracker_utcnow = _fake_utcnow
    event_helper.time_tracker_timestamp = _fake_timestamp
    dt_util.utcnow = _fake_dt_utcnow
    dt_util.now = _fake_dt_now  # type: ignore[assignment]
    _LOGGER.info("[ha_test_harness] Monkey-patched time tracker and dt_util functions for fake time support")


def _fire_time_changed(hass: HomeAssistant, utc_datetime: datetime) -> None:
    """Fire scheduled timers that are now due after time advance.

    Mirrors HA's async_fire_time_changed logic from tests/common.py.
    Iterates scheduled timers and fires those that are now in the past.
    """
    timestamp = utc_datetime.timestamp()
    loop = hass.loop

    for task in list(loop._scheduled):
        if not isinstance(task, asyncio.TimerHandle):
            continue
        if task.cancelled():
            continue

        mock_seconds_into_future = timestamp - time.time()
        future_seconds = task.when() - (loop.time() + 0.0001)

        if mock_seconds_into_future >= future_seconds:
            task._run()
            task.cancel()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/set",
        vol.Required("time"): str,
    }
)
@websocket_api.async_response
async def ws_set_time(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/set WebSocket command.

    Sets the fake time to an absolute value. Calculates the offset from real time
    and fires scheduled timers that are now due.
    """
    time_str: str = msg["time"]

    try:
        target_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        else:
            target_time = target_time.astimezone(timezone.utc)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_time", f"Invalid time format: {time_str!r}: {err}")
        return

    now = datetime.now(timezone.utc)
    offset = target_time - now
    hass.data[DOMAIN]["time_offset"] = offset

    _LOGGER.info("[ha_test_harness] Time set to %s (offset: %s)", target_time.isoformat(), offset)

    _fire_time_changed(hass, target_time)
    await hass.async_block_till_done()

    connection.send_result(msg["id"], {"time": target_time.isoformat(), "offset_seconds": offset.total_seconds()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/advance",
        vol.Required("seconds"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_advance_time(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/advance WebSocket command.

    Advances the fake time by the specified number of seconds (can be fractional).
    Updates the offset and fires scheduled timers that are now due.
    """
    seconds: float = msg["seconds"]
    delta = timedelta(seconds=seconds)

    hass.data[DOMAIN]["time_offset"] += delta
    new_time = datetime.now(timezone.utc) + hass.data[DOMAIN]["time_offset"]

    _LOGGER.info("[ha_test_harness] Time advanced by %s seconds to %s", seconds, new_time.isoformat())

    _fire_time_changed(hass, new_time)
    await hass.async_block_till_done()

    connection.send_result(msg["id"], {"time": new_time.isoformat(), "offset_seconds": hass.data[DOMAIN]["time_offset"].total_seconds()})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_test_harness/time/get",
    }
)
@websocket_api.async_response
async def ws_get_time(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Handle ha_test_harness/time/get WebSocket command.

    Returns the current fake time and offset from real time.
    """
    fake_time = datetime.now(timezone.utc) + hass.data[DOMAIN]["time_offset"]
    offset = hass.data[DOMAIN]["time_offset"]

    connection.send_result(
        msg["id"],
        {
            "time": fake_time.isoformat(),
            "offset_seconds": offset.total_seconds(),
        },
    )
