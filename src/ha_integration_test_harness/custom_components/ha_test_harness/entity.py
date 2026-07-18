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
from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature
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
    """A virtual light entity with full HA light contract support."""

    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS, ColorMode.RGB, ColorMode.XY}
    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.FLASH | LightEntityFeature.EFFECT

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual light entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'light.test_lamp').
            state: Initial state string ('on' or 'off').
            attributes: Initial extra attributes. May include light-specific keys:
                brightness, color_temp_kelvin, hs_color, rgb_color, rgbw_color,
                rgbww_color, xy_color, effect, effect_list, flash, transition.
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._is_on_state = state.lower() == "on"
        self._virtual_attributes: dict[str, Any] = dict(attributes)
        self._current_color_mode: ColorMode | None = None
        self._update_color_mode()

    def _update_color_mode(self) -> None:
        """Update color_mode based on the most recently set attribute."""
        if not self._is_on_state:
            self._current_color_mode = None
            return
        if "xy_color" in self._virtual_attributes and self._virtual_attributes["xy_color"] is not None:
            self._current_color_mode = ColorMode.XY
        elif "rgbww_color" in self._virtual_attributes and self._virtual_attributes["rgbww_color"] is not None:
            self._current_color_mode = ColorMode.RGBWW
        elif "rgbw_color" in self._virtual_attributes and self._virtual_attributes["rgbw_color"] is not None:
            self._current_color_mode = ColorMode.RGBW
        elif "rgb_color" in self._virtual_attributes and self._virtual_attributes["rgb_color"] is not None:
            self._current_color_mode = ColorMode.RGB
        elif "hs_color" in self._virtual_attributes and self._virtual_attributes["hs_color"] is not None:
            self._current_color_mode = ColorMode.HS
        elif "color_temp_kelvin" in self._virtual_attributes and self._virtual_attributes["color_temp_kelvin"] is not None:
            self._current_color_mode = ColorMode.COLOR_TEMP
        else:
            self._current_color_mode = ColorMode.COLOR_TEMP

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
    def color_mode(self) -> ColorMode | None:
        """Return the current color mode."""
        return self._current_color_mode

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return self._virtual_attributes.get("hs_color")

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._virtual_attributes.get("rgb_color")

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        return self._virtual_attributes.get("rgbw_color")

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value [int, int, int, int, int]."""
        return self._virtual_attributes.get("rgbww_color")

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the xy color value [float, float]."""
        return self._virtual_attributes.get("xy_color")

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._virtual_attributes.get("effect")

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._virtual_attributes.get("effect_list")

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes (excluding light-specific keys handled as properties)."""
        light_keys = {"brightness", "color_temp_kelvin", "hs_color", "rgb_color", "rgbw_color", "rgbww_color", "xy_color", "effect", "effect_list", "flash", "transition"}
        return {k: v for k, v in self._virtual_attributes.items() if k not in light_keys}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, handling all supported attributes."""
        self._is_on_state = True
        for key in ["brightness", "color_temp_kelvin", "hs_color", "rgb_color", "rgbw_color", "rgbww_color", "xy_color", "effect", "flash", "transition"]:
            if key in kwargs:
                self._virtual_attributes[key] = kwargs[key]
        self._update_color_mode()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off, handling transition and flash."""
        self._is_on_state = False
        for key in ["transition", "flash"]:
            if key in kwargs:
                self._virtual_attributes[key] = kwargs[key]
        self._update_color_mode()
        self.async_write_ha_state()

    def set_virtual_state(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        """Update the entity state and optionally attributes, then push to HA.

        Args:
            state: New state string ('on' or 'off').
            attributes: If provided, replaces all extra attributes. May include
                light-specific keys (brightness, color_temp_kelvin, hs_color, etc.).
        """
        self._is_on_state = state.lower() == "on"
        if attributes is not None:
            self._virtual_attributes = dict(attributes)
        self._update_color_mode()
        self.async_write_ha_state()


class VirtualMediaPlayerEntity(MediaPlayerEntity):
    """A virtual media player entity with programmatically controlled state.

    Supports turn_on/turn_off, playback transport (play_media, play, pause, stop,
    play_pause, next_track, previous_track, seek), and volume (set, up, down, mute)
    actions. State and attributes can be set directly via set_virtual_state().
    """

    _attr_should_poll = False
    _VOLUME_STEP: float = 0.1
    _attr_supported_features: MediaPlayerEntityFeature = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

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
        self._media_content_id: str | None = None
        self._media_content_type: str | None = None
        self._media_track: int = 0
        self._media_position: float | None = None
        self._volume_level: float | None = None
        self._is_volume_muted: bool = False
        if "volume_level" in attributes:
            self._volume_level = float(attributes["volume_level"])
        if "is_volume_muted" in attributes:
            self._is_volume_muted = bool(attributes["is_volume_muted"])

    @property
    def is_on(self) -> bool | None:
        """Return True if the media player is on."""
        return self._is_on_state

    @property
    def state(self) -> str | None:
        """Return the current media player state string."""
        return self._virtual_state

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 to 1.0)."""
        return self._volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if the media player is muted."""
        return self._is_volume_muted

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID currently playing."""
        return self._media_content_id

    @property
    def media_content_type(self) -> str | None:
        """Return the content type (e.g. music, video)."""
        return self._media_content_type

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra state attributes including media track and position."""
        attrs: dict[str, Any] = dict(self._virtual_attributes)
        attrs["media_track"] = self._media_track
        if self._media_position is not None:
            attrs["media_position"] = self._media_position
        return attrs

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

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Play media — auto-powers-on and transitions to 'playing'."""
        self._is_on_state = True
        self._virtual_state = "playing"
        self._media_content_type = media_type
        self._media_content_id = media_id
        self._media_track = 0
        self._media_position = None
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Resume playback — no-op if off."""
        if self._virtual_state in ("paused", "idle"):
            self._virtual_state = "playing"
            self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Pause playback — no-op unless playing."""
        if self._virtual_state == "playing":
            self._virtual_state = "paused"
            self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop playback — transitions to idle and clears media metadata."""
        if self._virtual_state in ("playing", "paused"):
            self._virtual_state = "idle"
            self._media_content_id = None
            self._media_content_type = None
            self._media_track = 0
            self._media_position = None
            self.async_write_ha_state()

    async def async_media_play_pause(self) -> None:
        """Toggle between play and pause — no-op if off."""
        if self._virtual_state == "playing":
            self._virtual_state = "paused"
            self.async_write_ha_state()
        elif self._virtual_state in ("paused", "idle"):
            self._virtual_state = "playing"
            self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Skip to next track — increments media_track attribute."""
        self._media_track += 1
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        """Go to previous track — decrements media_track, clamped at 0."""
        self._media_track = max(0, self._media_track - 1)
        self.async_write_ha_state()

    async def async_media_seek(self, position: float) -> None:
        """Seek to position — sets media_position attribute."""
        self._media_position = position
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level — clamped to 0.0-1.0."""
        self._volume_level = max(0.0, min(1.0, volume))
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Increase volume by step — clamped to 1.0."""
        current = self._volume_level if self._volume_level is not None else 0.0
        self._volume_level = min(1.0, current + self._VOLUME_STEP)
        self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Decrease volume by step — clamped to 0.0."""
        current = self._volume_level if self._volume_level is not None else 0.0
        self._volume_level = max(0.0, current - self._VOLUME_STEP)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the media player."""
        self._is_volume_muted = mute
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
            if "media_content_id" in attributes:
                self._media_content_id = attributes["media_content_id"]
            if "media_content_type" in attributes:
                self._media_content_type = attributes["media_content_type"]
            if "media_track" in attributes:
                self._media_track = attributes["media_track"]
            if "media_position" in attributes:
                self._media_position = attributes["media_position"]
            if "volume_level" in attributes:
                self._volume_level = float(attributes["volume_level"])
            if "is_volume_muted" in attributes:
                self._is_volume_muted = bool(attributes["is_volume_muted"])
        self.async_write_ha_state()


class VirtualSelectEntity(SelectEntity):
    """A virtual select entity with programmatically controlled state and options."""

    _attr_should_poll = False

    def __init__(self, unique_id: str, entity_id: str, state: str, attributes: dict[str, Any]) -> None:
        """Initialise the virtual select entity.

        Args:
            unique_id: Unique ID for the entity registry entry.
            entity_id: Desired entity ID (e.g. 'select.house_mode').
            state: Initial state string. If not in the options list, it is automatically added.
            attributes: Initial extra attributes. May include 'options' (a list of strings).
                If 'options' is not provided, defaults to ['unknown'].
        """
        self._attr_unique_id = unique_id
        self._attr_suggested_object_id = entity_id.split(".", 1)[1]
        self._attr_name = entity_id.split(".", 1)[1]
        self._virtual_state = state
        self._options: list[str] = list(attributes.get("options", ["unknown"]))
        if state not in self._options:
            self._options.append(state)
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
            state: New state string. If not in the current options list, it is automatically added.
            attributes: If provided, replaces all extra attributes. If it contains
                a new 'options' list, self._options is updated accordingly.
        """
        self._virtual_state = state
        if attributes is not None:
            if "options" in attributes:
                self._options = list(attributes["options"])
            self._virtual_attributes = dict(attributes)
        if state not in self._options:
            self._options.append(state)
        self.async_write_ha_state()
