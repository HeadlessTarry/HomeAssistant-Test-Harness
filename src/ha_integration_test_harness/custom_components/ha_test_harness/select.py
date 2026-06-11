"""Select platform for the HA Test Harness integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "ha_test_harness"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the select platform and register the async_add_entities callback.

    Args:
        hass: The Home Assistant instance.
        config: Platform configuration (unused).
        async_add_entities: Callback to add entities to this platform.
        discovery_info: Discovery data from async_load_platform; must contain 'domain'.
    """
    if discovery_info is None:
        return
    domain: str = discovery_info["domain"]
    hass.data[DOMAIN]["add_callbacks"][domain] = async_add_entities
    hass.data[DOMAIN]["platform_ready"][domain].set()


async def async_setup_entry(hass: HomeAssistant, config_entry: Any, async_add_entities: AddEntitiesCallback) -> None:
    """Not used — this integration is configured via configuration.yaml only."""
