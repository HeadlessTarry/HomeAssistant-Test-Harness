"""Virtual entity classes for the HA Test Harness integration."""

# mypy: disable-error-code="override"
# HA stubs define base class properties (is_on, extra_state_attributes, native_value, brightness)
# with structural constraints that mypy flags as [override] errors even when return types match.
# These classes are valid HA entities at runtime — the errors are false positives from the stubs.

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import ToggleEntity


class VirtualSensorEntity(SensorEntity):
    """A virtual sensor entity with programmatically controlled state."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual sensor.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'sensor.test_temp').
            state: Initial state string.
            attributes: Initial extra attributes.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._virtual_state = state
        self._virtual_attributes: dict[str, Any] = dict(attributes)

    @property
    def native_value(self) -> str | int | float | None | date | datetime | Decimal:
        """Return the sensor value."""
        return self._virtual_state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return self._virtual_attributes

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string.
            attributes: If provided, replaces all extra attributes.
        """
        self._virtual_state = state
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
        self.async_write_ha_state()


class VirtualBinarySensorEntity(BinarySensorEntity):
    """A virtual binary sensor entity with programmatically controlled state."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual binary sensor.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'binary_sensor.motion').
            state: Initial state string ('on' or 'off').
            attributes: Initial extra attributes.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._is_on_state = state.lower() == "on"
        self._virtual_attributes: dict[str, Any] = dict(attributes)

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        return self._is_on_state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return self._virtual_attributes

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string ('on' or 'off').
            attributes: If provided, replaces all extra attributes.
        """
        self._is_on_state = state.lower() == "on"
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
        self.async_write_ha_state()


class VirtualToggleEntity(ToggleEntity):
    """A virtual toggle entity used for the switch and input_boolean domains."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual toggle entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'input_boolean.test_flag').
            state: Initial state string ('on' or 'off').
            attributes: Initial extra attributes.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._is_on_state = state.lower() == "on"
        self._virtual_attributes: dict[str, Any] = dict(attributes)

    @property
    def is_on(self) -> bool | None:
        """Return True if the toggle entity is on."""
        return self._is_on_state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes."""
        return self._virtual_attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._is_on_state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._is_on_state = False
        self.async_write_ha_state()

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string ('on' or 'off').
            attributes: If provided, replaces all extra attributes.
        """
        self._is_on_state = state.lower() == "on"
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
        self.async_write_ha_state()


class VirtualLightEntity(LightEntity):
    """A virtual light entity with brightness and colour temperature support."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual light entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'light.test_lamp').
            state: Initial state string ('on' or 'off').
            attributes: Initial extra attributes. May include 'brightness' (0-255)
                and/or 'color_temp_kelvin'.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._is_on_state = state.lower() == "on"
        self._virtual_attributes: dict[str, Any] = dict(attributes)
        self._update_color_modes()

    def _update_color_modes(self) -> None:
        """Derive supported_color_modes and color_mode from current attributes."""
        if "color_temp_kelvin" in self._virtual_attributes:
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif "brightness" in self._virtual_attributes:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        return self._is_on_state

    @property
    def brightness(self) -> int | None:
        """Return current brightness (0-255), or None if not set."""
        return self._virtual_attributes.get("brightness")

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return current colour temperature in Kelvin, or None if not set."""
        return self._virtual_attributes.get("color_temp_kelvin")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes (excluding light-specific keys handled as properties)."""
        return {k: v for k, v in self._virtual_attributes.items() if k not in ("brightness", "color_temp_kelvin")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally updating brightness/colour temperature."""
        self._is_on_state = True
        if "brightness" in kwargs:
            self._virtual_attributes["brightness"] = kwargs["brightness"]
        if "color_temp_kelvin" in kwargs:
            self._virtual_attributes["color_temp_kelvin"] = kwargs["color_temp_kelvin"]
        self._update_color_modes()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._is_on_state = False
        self.async_write_ha_state()

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string ('on' or 'off').
            attributes: If provided, replaces all extra attributes. May include
                'brightness' and/or 'color_temp_kelvin'.
        """
        self._is_on_state = state.lower() == "on"
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
            self._update_color_modes()
        self.async_write_ha_state()


class VirtualMediaPlayerEntity(MediaPlayerEntity):
    """A virtual media player entity with programmatically controlled state.

    Supports turn_on/turn_off actions and arbitrary state setting via set_virtual_state().
    Known limitations:
    - No play/pause, volume, mute, source, or media metadata support
    - No supported_features bitmask — HA will show a minimal media player card
    - async_turn_on() always transitions to "idle" (not "playing") since there is no media to resume
    - State can be set to any string via set_virtual_state(), but only standard MediaPlayerEntity
      states ("off", "idle", "playing", "paused", etc.) will integrate cleanly with HA UI
    """

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual media player entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'media_player.living_room_tv').
            state: Initial state string (e.g. 'off', 'idle', 'playing').
            attributes: Initial extra attributes.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._is_on_state = state.lower() != "off"
        self._virtual_state = state
        self._virtual_attributes: dict[str, Any] = dict(attributes)

    @property
    def is_on(self) -> bool | None:
        """Return True if the media player is on."""
        return self._is_on_state

    @property
    def state(self) -> str | None:
        """Return the current media player state string."""
        return self._virtual_state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes (passthrough, like VirtualSensorEntity)."""
        return self._virtual_attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the media player on, transitioning state to 'idle'."""
        self._is_on_state = True
        self._virtual_state = "idle"
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the media player off."""
        self._is_on_state = False
        self._virtual_state = "off"
        self.async_write_ha_state()

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string (e.g. 'off', 'idle', 'playing').
            attributes: If provided, replaces all extra attributes.
        """
        self._is_on_state = state.lower() != "off"
        self._virtual_state = state
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
        self.async_write_ha_state()


class VirtualSelectEntity(SelectEntity):
    """A virtual select entity with programmatically controlled state and options."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual select entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'select.house_mode').
            state: Initial state string (must be one of the options, or 'unknown' if no options).
            attributes: Initial extra attributes. May include 'options' (a list of strings).
                If 'options' is not provided, defaults to ['unknown'].
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._virtual_state = state
        self._options: list[str] = list(attributes.get("options", ["unknown"]))
        self._virtual_attributes: dict[str, Any] = dict(attributes)

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        return self._virtual_state

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self._options

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes (excluding the 'options' key, which is handled as a property)."""
        return {k: v for k, v in self._virtual_attributes.items() if k != "options"}

    async def async_select_option(self, option: str) -> None:
        """Select an option.

        Args:
            option: The option string to select. Must be in self._options.

        Raises:
            ValueError: If the option is not in the options list.
        """
        if option not in self._options:
            raise ValueError(f"Option {option!r} is not in the available options: {self._options}")
        self._virtual_state = option
        self.async_write_ha_state()

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string (should be one of the available options).
            attributes: If provided, replaces all extra attributes. If it contains
                a new 'options' list, self._options is updated accordingly.
        """
        self._virtual_state = state
        if attributes is not None:
            if "options" in attributes:
                self._options = list(attributes["options"])
            self._virtual_attributes = dict(attributes)
        self.async_write_ha_state()
