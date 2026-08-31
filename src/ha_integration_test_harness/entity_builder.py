"""Fluent builder API for test entity setup."""

from typing import TYPE_CHECKING, Any, Optional, Self

if TYPE_CHECKING:
    from .homeassistant_client import HomeAssistant


class EntityBuilder:
    """Fluent builder for configuring virtual entities.

    Provides a chainable API for setting up virtual entities with device classes,
    areas, labels, and custom attributes. Each method applies changes immediately
    via the underlying Home Assistant client.

    The builder is stateless — it delegates all operations to the HomeAssistant
    client instance that created it. Multiple builders can be created for the
    same entity_id; each operates independently.
    """

    def __init__(self, client: "HomeAssistant", entity_id: str, initial_attributes: Optional[dict[str, Any]] = None) -> None:
        """Initialize the EntityBuilder.

        Args:
            client: The HomeAssistant client instance.
            entity_id: The entity ID being configured.
            initial_attributes: Optional initial attributes to track for merging.
        """
        self._client = client
        self._entity_id = entity_id
        self._attributes: dict[str, Any] = initial_attributes.copy() if initial_attributes else {}

    def _apply_attributes(self) -> None:
        """Apply tracked attributes to the entity via set_state()."""
        state_response = self._client.get_state(self._entity_id)
        current_state = state_response.get("state", "") if state_response else ""
        self._client.set_state(self._entity_id, current_state, self._attributes)

    def with_device_class(self, device_class: str) -> Self:
        """Set the device_class attribute for the entity.

        Args:
            device_class: The device class (e.g., "motion", "occupancy", "temperature").

        Returns:
            Self for method chaining.
        """
        self._attributes["device_class"] = device_class
        self._apply_attributes()
        return self

    def in_area(self, area: str, labels: Optional[list[str]] = None) -> Self:
        """Assign the entity to an area and optionally set labels.

        Triggers rollback tracking before the first area/label change to ensure
        the pre-test configuration can be restored.

        Args:
            area: The area ID to assign (e.g., "study", "living_room").
            labels: Optional list of label IDs to assign (e.g., ["presence", "security"]).

        Returns:
            Self for method chaining.
        """
        self._client._track_entity_config_for_rollback(self._entity_id)
        self._client._set_entity_area(self._entity_id, area)
        if labels is not None:
            self._client._set_entity_labels(self._entity_id, labels)
        return self

    def with_labels(self, labels: list[str]) -> Self:
        """Assign labels to the entity.

        Triggers rollback tracking before the first label change to ensure
        the pre-test configuration can be restored.

        Args:
            labels: The list of label IDs to assign (e.g., ["night_mode", "security"]).

        Returns:
            Self for method chaining.
        """
        self._client._track_entity_config_for_rollback(self._entity_id)
        self._client._set_entity_labels(self._entity_id, labels)
        return self

    def with_attributes(self, attributes: dict[str, Any]) -> Self:
        """Set custom attributes for the entity.

        Successive calls merge attributes — new attributes are added, existing
        ones are overwritten.

        Args:
            attributes: Dictionary of attribute names to values.

        Returns:
            Self for method chaining.
        """
        self._attributes.update(attributes)
        self._apply_attributes()
        return self
