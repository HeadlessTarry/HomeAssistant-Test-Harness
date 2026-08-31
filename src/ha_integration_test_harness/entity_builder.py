"""Fluent builder API for test entity setup."""

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from .homeassistant_client import HomeAssistant


class EntityBuilder:
    """Fluent builder for configuring virtual entities.

    Provides a chainable API for setting up virtual entities with device classes,
    areas, labels, and custom attributes. Each method applies changes immediately
    via the underlying Home Assistant client.

    The builder holds a local ``_attributes`` dict that accumulates attribute
    changes across chained calls. It delegates all I/O to the HomeAssistant
    client instance that created it.

    Each call to ``given_an_entity()`` returns a fresh builder. If multiple
    builders exist for the same entity_id, each tracks its own attributes
    independently — successive ``with_attributes()`` calls on one builder
    will not see attributes applied through another.
    """

    def __init__(self, client: "HomeAssistant", entity_id: str) -> None:
        """Initialize the EntityBuilder.

        Fetches the current remote state to initialize the local attributes dict.
        This ensures the builder starts with accurate state, whether the entity
        was just created or already exists.

        Args:
            client: The HomeAssistant client instance.
            entity_id: The entity ID being configured.
        """
        self._client = client
        self._entity_id = entity_id
        current_state = self._client.get_state(self._entity_id)
        self._attributes: dict[str, Any] = current_state.get("attributes", {}).copy() if current_state else {}

    def _apply_attributes(self) -> None:
        """Apply tracked attributes to the entity via set_state().

        Fetches current remote attributes and merges local attributes on top.
        This preserves any attributes set by other builders or external changes.
        """
        current_state = self._client.get_state(self._entity_id)
        remote_attributes = current_state.get("attributes", {}).copy() if current_state else {}
        remote_attributes.update(self._attributes)
        state_value = current_state.get("state", "") if current_state else ""
        self._client.set_state(self._entity_id, state_value, remote_attributes)

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

    def in_area(self, area: str) -> Self:
        """Assign the entity to an area.

        Triggers rollback tracking before the first area change to ensure
        the pre-test configuration can be restored.

        Args:
            area: The area ID to assign (e.g., "study", "living_room").

        Returns:
            Self for method chaining.
        """
        self._client._track_entity_config_for_rollback(self._entity_id)
        self._client._set_entity_area(self._entity_id, area)
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
