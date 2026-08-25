"""Home Assistant API client."""

import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional, Union, overload
from urllib.parse import urlparse, urlunparse

import requests
import websocket

from .exceptions import HomeAssistantClientError, HomeAssistantTimeoutError

logger = logging.getLogger(__name__)

_HEALTH_CHECK_TIMEOUT = 3
_HEALTH_CHECK_POLL_TIMEOUT = 10
_HEALTH_CHECK_INITIAL_INTERVAL = 0.1
_HEALTH_CHECK_MAX_INTERVAL = 1.0

_API_RETRY_MAX_RETRIES = 3
_API_RETRY_INITIAL_INTERVAL = 0.5

# Sentinel object used to distinguish "not provided" from ``None`` in optional parameters.
# Typed as ``Any`` so mypy accepts it as a default for parameters typed ``Optional[str]``
# or ``Optional[list[str]]`` without raising an incompatible-default-value error.
_UNSET: Any = object()


class HomeAssistant:
    """Client for interacting with Home Assistant API.

    Provides methods for managing entity states using a long-lived access token
    for authentication.
    """

    def __init__(self, base_url: str, access_token: str, timeout: int = 10) -> None:
        """Initialize the Home Assistant client.

        Args:
            base_url: The base URL of the Home Assistant instance.
            access_token: The long-lived access token for authentication.
            timeout: Default timeout in seconds for HTTP requests (default: 10).
        """
        self._base_url = base_url
        self._access_token = access_token
        self._timeout = timeout
        self._created_entities: set[str] = set()
        self._entity_original_config: dict[str, dict[str, Any]] = {}
        self._entity_original_state: dict[str, Optional[dict[str, Any]]] = {}
        self._frozen_template_entities: set[str] = set()
        self._known_area_ids: Optional[set[str]] = None
        self._known_label_ids: Optional[set[str]] = None
        self._is_unresponsive: bool = False
        self._test_start_time: Optional[datetime] = None

    def _retry_on_transient_failure(self, func: Callable[[], Any], operation_description: str) -> Any:
        """Retry an operation on transient network failures with exponential backoff.

        Retries on ``requests.Timeout`` and ``requests.ConnectionError`` only.
        Other exceptions are raised immediately.

        Args:
            func: The callable to retry.
            operation_description: Description for error messages.

        Returns:
            The return value of the callable.

        Raises:
            HomeAssistantTimeoutError: If all retries are exhausted on timeout.
            HomeAssistantClientError: If all retries are exhausted on connection error,
                or if a non-transient exception occurs.
        """
        interval = _API_RETRY_INITIAL_INTERVAL
        last_exception: Optional[Exception] = None

        for attempt in range(_API_RETRY_MAX_RETRIES + 1):
            try:
                return func()
            except requests.Timeout as e:
                last_exception = e
                if attempt < _API_RETRY_MAX_RETRIES:
                    logger.debug(f"{operation_description}: timeout on attempt {attempt + 1}, retrying in {interval}s")
                    time.sleep(interval)
                    interval *= 2
                else:
                    raise HomeAssistantTimeoutError(f"{operation_description}: timed out after {_API_RETRY_MAX_RETRIES + 1} attempts: {e}")
            except requests.ConnectionError as e:
                last_exception = e
                if attempt < _API_RETRY_MAX_RETRIES:
                    logger.debug(f"{operation_description}: connection error on attempt {attempt + 1}, retrying in {interval}s")
                    time.sleep(interval)
                    interval *= 2
                else:
                    raise HomeAssistantClientError(f"{operation_description}: connection failed after {_API_RETRY_MAX_RETRIES + 1} attempts: {e}")
            except requests.RequestException as e:
                raise HomeAssistantClientError(f"{operation_description}: {e}")

        raise HomeAssistantClientError(f"{operation_description}: failed after {_API_RETRY_MAX_RETRIES + 1} attempts: {last_exception}")

    @property
    def is_unresponsive(self) -> bool:
        """Whether Home Assistant has been confirmed unresponsive.

        Set to ``True`` after ``check_health()`` determines the API is unreachable.
        Once set, the pytest plugin skips remaining tests and suppresses futile cleanup.
        """
        return self._is_unresponsive

    def set_state(self, entity_id: str, state: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Set the state and/or attributes of a Home Assistant entity.

        If the entity was created via ``given_an_entity()``, the update is routed through
        the bundled ``ha_test_harness`` custom integration via WebSocket, which preserves
        the entity's registration in the entity registry.

        Otherwise, the state is injected directly via the REST API (``POST /api/states``).
        REST-injected entities are written only to the HA state machine — they are **not**
        registered in the entity registry and cannot be used with ``given_entity_has()``.

        Before the first ``set_state()`` call per entity per test, the current state is
        snapshot and will be automatically restored after the test completes. If the entity
        didn't exist before ``set_state()`` was called, it will be removed at teardown.

        Args:
            entity_id: The entity ID to set the state for (e.g., 'light.living_room').
            state: The state value to set for the entity.
            attributes: Optional dictionary of attributes to set for the entity.

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        if entity_id not in self._entity_original_state:
            self._entity_original_state[entity_id] = self.get_state(entity_id)

        self._apply_state(entity_id, state, attributes)

    def _apply_state(self, entity_id: str, state: str, attributes: Optional[dict[str, Any]] = None, *, _freeze: bool = True) -> None:
        """Apply state and/or attributes to an entity via the appropriate mechanism.

        Routes the state update through WebSocket for entities created via ``given_an_entity()``
        (to preserve entity registry registration), or through REST API for other entities.

        Args:
            entity_id: The entity ID to update.
            state: The state value to set.
            attributes: Optional dictionary of attributes to set.
            _freeze: Whether to freeze the entity after applying state (internal use only).

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails.
        """
        if entity_id in self._created_entities:
            payload: dict[str, Any] = {"id": 1, "type": "ha_test_harness/entity/set_state", "entity_id": entity_id, "state": state}
            if attributes is not None:
                payload["attributes"] = attributes
            response = self._ws_send_receive(payload)
            if not response.get("success"):
                raise HomeAssistantClientError(f"Failed to set state for entity {entity_id} via ha_test_harness: {response}")
            return

        url = f"{self._base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        body: dict[str, Any] = {"state": state}
        if attributes is not None:
            body["attributes"] = attributes

        def do_post() -> requests.Response:
            response_http = requests.post(url, json=body, headers=headers, timeout=self._timeout)
            response_http.raise_for_status()
            return response_http

        self._retry_on_transient_failure(do_post, f"POST {url}")

        if _freeze:
            self._freeze_template_entity(entity_id)

    def get_state(self, entity_id: str) -> Optional[dict[str, Any]]:
        """Get the state of an entity from Home Assistant.

        Args:
            entity_id: The entity ID to query (e.g., "light.foobar").

        Returns:
            The state dictionary of the entity, or None if not found (404 response).

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        url = f"{self._base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        def do_get() -> Optional[dict[str, Any]]:
            response = requests.get(url, headers=headers, timeout=self._timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        result = self._retry_on_transient_failure(do_get, f"GET {url}")
        return result if result is None else dict(result)

    def get_config(self) -> dict[str, Any]:
        """Fetch the Home Assistant configuration.

        Returns:
            The configuration dictionary from ``GET /api/config``.
            Relevant keys include ``time_zone`` (IANA timezone name, e.g. ``"Europe/London"``),
            ``latitude``, ``longitude``, and ``unit_system``.

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        url = f"{self._base_url}/api/config"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        def do_get() -> dict[str, Any]:
            response = requests.get(url, headers=headers, timeout=self._timeout)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        result = self._retry_on_transient_failure(do_get, f"GET {url}")
        return dict(result)

    @overload
    def assert_entity_state(self, entity_id: str, expected_state: str, expected_attributes: Optional[dict[str, Any]] = None, timeout: int = 5) -> None: ...

    @overload
    def assert_entity_state(self, entity_id: str, expected_state: Callable[[str], bool], expected_attributes: Optional[dict[str, Any]] = None, timeout: int = 5) -> None: ...

    @overload
    def assert_entity_state(self, entity_id: str, expected_state: None = None, expected_attributes: Optional[dict[str, Any]] = None, timeout: int = 5) -> None: ...

    def assert_entity_state(
        self,
        entity_id: str,
        expected_state: Union[str, Callable[[str], bool], None] = None,
        expected_attributes: Optional[dict[str, Any]] = None,
        timeout: int = 5,
    ) -> None:
        """Assert that an entity is in the expected state and/or has the expected attributes.

        Polls the entity state every second until all conditions are met or the timeout is reached.
        At least one of ``expected_state`` or ``expected_attributes`` must be provided.

        Args:
            entity_id: The entity ID to check (e.g., "light.foobar").
            expected_state: Either a string for exact match, or a callable that takes the current
                state string and returns True when satisfied. Pass None (or omit) to skip state checking.
            timeout: Maximum time to wait in seconds (default: 5).
            expected_attributes: Optional dictionary of attribute name to expected value. Each value
                may be an exact value (compared with ``==``) or a callable predicate that takes the
                actual attribute value and returns True when satisfied. Only the attributes listed here
                are checked; any additional attributes on the entity are ignored.

        Raises:
            ValueError: If neither ``expected_state`` nor ``expected_attributes`` is provided.
            AssertionError: If the entity is not found, or if state/attributes do not match within
                the timeout period.
        """
        if expected_state is None and expected_attributes is None:
            raise ValueError("At least one of expected_state or expected_attributes must be provided")

        start_time = time.time()
        last_state = None
        state_desc = "predicate function" if callable(expected_state) else f"'{expected_state}'"

        while True:
            state_response = self.get_state(entity_id)

            if state_response is None:
                raise AssertionError(f"Entity {entity_id} not found")

            if not isinstance(state_response, dict):
                raise AssertionError(f"Unexpected state response format for entity {entity_id}: {state_response}")

            # Extract the actual state value from the response
            current_state = state_response.get("state")
            if not isinstance(current_state, str):
                raise AssertionError(f"Entity {entity_id} has unexpected state value: {current_state}")

            # Check if state matches expectation
            state_matches = True
            if expected_state is not None:
                if callable(expected_state):
                    state_matches = expected_state(current_state)
                else:
                    state_matches = current_state == expected_state

            # Check if attributes match expectation
            attributes_match = True
            mismatched_attributes: dict[str, Any] = {}
            if expected_attributes is not None:
                current_attributes = state_response.get("attributes", {})
                for attr_name, attr_expected in expected_attributes.items():
                    attr_actual = current_attributes.get(attr_name)
                    if callable(attr_expected):
                        if not attr_expected(attr_actual):
                            attributes_match = False
                            mismatched_attributes[attr_name] = attr_actual
                    else:
                        if attr_actual != attr_expected:
                            attributes_match = False
                            mismatched_attributes[attr_name] = attr_actual

            if state_matches and attributes_match:
                if last_state is not None:
                    if expected_state is not None:
                        condition_desc = f"state {state_desc}"
                        if expected_attributes is not None:
                            condition_desc += " and expected attributes"
                    elif expected_attributes is not None:
                        attr_keys = ", ".join(sorted(expected_attributes.keys()))
                        condition_desc = f"expected attributes ({attr_keys})"
                    else:
                        condition_desc = "expected conditions"
                    logger.debug(f"Entity {entity_id} reached {condition_desc} after {time.time() - start_time:.1f}s")
                return

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                failure_parts = []
                if expected_state is not None and not state_matches:
                    failure_parts.append(f"state did not match {state_desc} (current: '{current_state}')")
                if expected_attributes is not None and not attributes_match:
                    attr_details = []
                    for k, v in mismatched_attributes.items():
                        expected_val = expected_attributes[k]
                        if callable(expected_val):
                            attr_details.append(f"'{k}': predicate not satisfied (actual: {v!r})")
                        else:
                            attr_details.append(f"'{k}': expected {expected_val!r}, got {v!r}")
                    failure_parts.append(f"attributes did not match ({'; '.join(attr_details)})")
                error_msg = f"Entity {entity_id} did not reach expected conditions within {timeout}s. " + "; ".join(failure_parts)
                diagnostics = self._build_assertion_diagnostics(entity_id)
                if diagnostics:
                    error_msg += "\n" + diagnostics
                raise AssertionError(error_msg)

            last_state = current_state
            time.sleep(1)

    def _get_state_history(self, entity_id: str, start_time: datetime, end_time: datetime) -> Optional[list[dict[str, Any]]]:
        from datetime import timezone

        # Ensure timestamps are timezone-aware UTC
        if start_time.tzinfo is None:
            # Assume naive datetime is local time, convert to UTC
            start_time = start_time.astimezone(timezone.utc)
        if end_time.tzinfo is None:
            # Assume naive datetime is local time, convert to UTC
            end_time = end_time.astimezone(timezone.utc)

        url = f"{self._base_url}/api/history/period/{start_time.isoformat()}"
        params = {"filter_entity_id": entity_id, "end": end_time.isoformat()}
        logger.info(f"Querying history for {entity_id}: {url} with params {params}")
        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            response = requests.get(url, headers=headers, params=params, timeout=self._timeout)
            response.raise_for_status()
            result: list[list[dict[str, Any]]] = response.json()
            if result and len(result) > 0:
                return result[0]
            return []
        except Exception as e:
            logger.warning(f"Failed to get state history for {entity_id}: {e}")
            return None

    def _build_assertion_diagnostics(self, entity_id: str) -> str:
        if self._test_start_time is None:
            return ""
        end_time = datetime.now()
        history = self._get_state_history(entity_id, self._test_start_time, end_time)
        return self._format_state_history(history, self._test_start_time)

    def _format_timestamp(self, ts_str: str, test_start_time: datetime) -> tuple[str, str]:
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            ts = test_start_time
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        relative = (ts - test_start_time).total_seconds()
        relative_str = f"+{relative:.1f}s" if relative >= 0 else f"{relative:.1f}s"
        absolute_str = ts.strftime("%H:%M:%S")
        return absolute_str, relative_str

    def _compute_attr_deltas(self, prev_attrs: dict[str, Any], current_attrs: dict[str, Any]) -> list[str]:
        attr_parts: list[str] = []
        all_attr_keys = set(prev_attrs.keys()) | set(current_attrs.keys())
        for key in sorted(all_attr_keys):
            old_val = prev_attrs.get(key)
            new_val = current_attrs.get(key)
            if key not in prev_attrs:
                attr_parts.append(f"{key}: {new_val!r} (new)")
            elif key not in current_attrs:
                attr_parts.append(f"{key}: (removed)")
            elif old_val != new_val:
                attr_parts.append(f"{key}: {old_val!r}→{new_val!r}")
        return attr_parts

    def _get_state_prefix(self, state: str, index: int, total_transitions: int, max_transitions: int) -> str:
        if state == "unavailable" and index > 0:
            return " [unregistered]"
        if index == 0 and total_transitions <= max_transitions and state in ("unavailable", "unknown"):
            return " [created]"
        return ""

    def _format_state_history(self, history: Optional[list[dict[str, Any]]], test_start_time: datetime) -> str:
        if history is None:
            return "State change history unavailable."
        if not history:
            return "No state changes recorded during this test."

        max_transitions = 10
        total_transitions = len(history)
        shown_entries = history[-max_transitions:] if total_transitions > max_transitions else history
        omitted = total_transitions - max_transitions if total_transitions > max_transitions else 0

        lines: list[str] = []
        prev_attrs: dict[str, Any] = {}

        for i, entry in enumerate(shown_entries):
            ts_str = entry.get("last_changed", entry.get("last_updated", ""))
            absolute_str, relative_str = self._format_timestamp(ts_str, test_start_time)
            state = entry.get("state", "")
            current_attrs = entry.get("attributes", {})
            prefix = self._get_state_prefix(state, i, total_transitions, max_transitions)
            attr_parts = self._compute_attr_deltas(prev_attrs, current_attrs)

            line = f"  [{absolute_str}] ({relative_str}) {state}{prefix}"
            if attr_parts:
                line += f" | {', '.join(attr_parts)}"
            lines.append(line)
            prev_attrs = dict(current_attrs)

        result_lines: list[str] = ["State change history:"]
        if omitted > 0:
            result_lines.append(f"  … and {omitted} more changes")
        result_lines.extend(lines)
        return "\n".join(result_lines)

    def remove_entity(self, entity_id: str) -> None:
        """Remove an entity from Home Assistant.

        If the entity was created via ``given_an_entity()``, it is removed via the
        bundled ``ha_test_harness`` custom integration WebSocket command, which deletes
        the entity from both the state machine and the entity registry. This operation
        is idempotent — if the entity is not found the command still succeeds.

        Otherwise, the entity is removed via the REST API (``DELETE /api/states``), which
        removes it from the state machine only (no entity registry entry to clean up).

        Args:
            entity_id: The entity ID to remove (e.g., 'light.living_room').

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        if entity_id in self._created_entities:
            payload: dict[str, Any] = {"id": 1, "type": "ha_test_harness/entity/delete", "entity_id": entity_id}
            response = self._ws_send_receive(payload)
            if not response.get("success"):
                raise HomeAssistantClientError(f"Failed to remove entity {entity_id} via ha_test_harness: {response}")
            self._forget_entity(entity_id)
            return

        url = f"{self._base_url}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        def do_delete() -> None:
            response_http = requests.delete(url, headers=headers, timeout=self._timeout)
            if response_http.status_code != 404:
                response_http.raise_for_status()

        self._retry_on_transient_failure(do_delete, f"DELETE {url}")
        self._forget_entity(entity_id)

    def _forget_entity(self, entity_id: str) -> None:
        """Remove an entity from internal tracking dictionaries.

        Called after successful entity removal to prevent test rollback from attempting
        to restore state or clean up an entity that no longer exists.

        Args:
            entity_id: The entity ID to remove from tracking.
        """
        self._created_entities.discard(entity_id)
        self._entity_original_state.pop(entity_id, None)

    def call_action(self, domain: str, action: str, data: Optional[dict[str, Any]] = None) -> None:
        """Call a Home Assistant action (service).

        Args:
            domain: The domain of the action (e.g., 'light', 'switch', 'input_boolean').
            action: The action to call (e.g., 'turn_on', 'turn_off', 'toggle').
            data: Optional dictionary of action data (e.g., {'entity_id': 'light.living_room'}).

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        url = f"{self._base_url}/api/services/{domain}/{action}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        def do_post() -> None:
            response = requests.post(url, json=data or {}, headers=headers, timeout=self._timeout)
            response.raise_for_status()

        self._retry_on_transient_failure(do_post, f"POST {url}")

    def call_action_with_response(self, domain: str, action: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Call a Home Assistant action (service) and return its response.

        Args:
            domain: The domain of the action (e.g., 'light', 'switch', 'ai_task').
            action: The action to call (e.g., 'turn_on', 'generate_data').
            data: Optional dictionary of action data.

        Returns:
            The service response dictionary from the service call.

        Raises:
            HomeAssistantTimeoutError: If the request times out.
            HomeAssistantClientError: If the request fails due to network issues or API errors.
        """
        url = f"{self._base_url}/api/services/{domain}/{action}?return_response"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        def do_post() -> dict[str, Any]:
            response = requests.post(url, json=data or {}, headers=headers, timeout=self._timeout)
            if response.status_code >= 400:
                raise HomeAssistantClientError(f"Failed to call action {domain}.{action} at {url}: {response.status_code} {response.reason}\n" + f"Response body: {response.text}")
            response_json = response.json()
            service_response = response_json.get("service_response", response_json)
            assert isinstance(service_response, dict)
            return dict(service_response)

        result = self._retry_on_transient_failure(do_post, f"POST {url}")
        return dict(result)

    def check_health(self) -> bool:
        """Check whether Home Assistant is responsive.

        Polls ``GET /api/config`` with exponential backoff (0.1s → 1s max interval),
        up to a total timeout of 10 seconds. Validates that the response is valid JSON.
        Returns ``True`` if the API responds with HTTP 200 and valid JSON, ``False`` otherwise.
        On failure, sets ``_is_unresponsive`` to ``True`` so the pytest plugin can
        skip remaining tests and suppress futile cleanup.

        This method never raises — it is purely diagnostic, but has the side-effect
        of marking the client as unresponsive on failure.

        Returns:
            ``True`` if Home Assistant is responsive, ``False`` if unreachable.
        """
        url = f"{self._base_url}/api/config"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        start_time = time.time()
        interval = _HEALTH_CHECK_INITIAL_INTERVAL

        while True:
            try:
                response = requests.get(url, headers=headers, timeout=_HEALTH_CHECK_TIMEOUT)
                if response.status_code == 200:
                    response.json()
                    return True
                if response.status_code == 401:
                    return True
            except requests.RequestException:
                pass

            elapsed = time.time() - start_time
            if elapsed >= _HEALTH_CHECK_POLL_TIMEOUT:
                self._is_unresponsive = True
                return False

            time.sleep(interval)
            interval = min(interval * 2, _HEALTH_CHECK_MAX_INTERVAL)

    def given_an_entity(self, entity_id: str, state: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Create a fully-registered entity for testing purposes with automatic cleanup.

        Creates the entity via the bundled ``ha_test_harness`` custom integration using
        a WebSocket command. The entity is registered in the HA entity registry (it has a
        ``unique_id``), appears in the HA UI, and supports area/label assignment via
        ``given_entity_has()``. Supported domains: ``sensor``, ``binary_sensor``,
        ``switch``, ``light``, ``media_player``, ``select``.

        If called a second time with the same ``entity_id``, the existing entity's state
        is updated in place (equivalent to calling ``set_state()``). The entity is tracked
        for automatic cleanup at the end of the test regardless.

        Args:
            entity_id: The entity ID to create (e.g., 'sensor.test_temp'). The domain prefix
                must be one of the supported domains listed above.
            state: The initial state value for the entity.
            attributes: Optional dictionary of attributes to set for the entity.

        Raises:
            HomeAssistantClientError: If the entity could not be created, or if the domain
                is not supported by the ha_test_harness integration.
        """
        if entity_id in self._created_entities:
            # Entity already exists — update its state in place.
            self.set_state(entity_id, state, attributes)
            return

        payload: dict[str, Any] = {"id": 1, "type": "ha_test_harness/entity/create", "entity_id": entity_id, "state": state}
        if attributes is not None:
            payload["attributes"] = attributes
        # Use a generous timeout: the server-side handler waits up to 30s for the platform to be
        # ready (e.g. on the very first entity creation after HA starts), so the socket timeout must
        # exceed that to avoid a spurious WebSocket timeout error.
        response = self._ws_send_receive(payload, timeout=60)
        if not response.get("success"):
            raise HomeAssistantClientError(f"Failed to create entity {entity_id} via ha_test_harness: {response}")
        self._created_entities.add(entity_id)

    def _ws_send_receive(self, payload: dict[str, Any], timeout: int = 10) -> dict[str, Any]:
        """Authenticate over the WebSocket API and send a single command, returning the response.

        Opens a new WebSocket connection for each call, performs the HA authentication
        handshake, sends ``payload``, and returns the result message.

        Note: A new TCP connection and auth exchange is opened per call. Operations like
        ``given_an_entity()`` followed by ``given_entity_has()`` in the same test will each
        open their own connection. This is acceptable for a test harness, but if suite startup
        latency becomes a concern, consider introducing a persistent/reusable connection.

        Args:
            payload: The command payload to send. Must include an ``"id"`` field.
            timeout: Socket timeout in seconds (default 10). Pass a larger value for commands
                that may block server-side (e.g. waiting for a platform to become ready).

        Returns:
            The response message dict returned by Home Assistant.

        Raises:
            HomeAssistantTimeoutError: If the WebSocket connection or command times out.
            HomeAssistantClientError: If the connection, authentication, or command fails.
        """
        ws_parsed = urlparse(self._base_url)
        ws_scheme = "wss" if ws_parsed.scheme == "https" else "ws"
        ws_url = urlunparse(ws_parsed._replace(scheme=ws_scheme, path="/api/websocket"))
        ws = websocket.WebSocket()
        try:
            ws.connect(ws_url, timeout=timeout)  # type: ignore[no-untyped-call]

            # Use a short timeout for the auth handshake: on a healthy HA instance the
            # auth_required and auth_ok messages arrive in well under a second.  The full
            # `timeout` is only needed for the command response, which may block server-side
            # (e.g. waiting for a platform to become ready on the first entity/create call).
            # Without this split, ws.connect(timeout=60) sets sock.settimeout(60) globally,
            # and all three recv() calls independently inherit that ceiling — worst case
            # 3 × 60 s = 180 s before a connection problem surfaces.
            ws.sock.settimeout(10)  # type: ignore[union-attr]

            # Receive auth_required
            auth_required = json.loads(ws.recv())
            if auth_required.get("type") != "auth_required":
                raise HomeAssistantClientError(f"Unexpected WebSocket message during handshake: {auth_required}")

            # Send auth
            ws.send(json.dumps({"type": "auth", "access_token": self._access_token}))

            # Receive auth_ok
            auth_result = json.loads(ws.recv())
            if auth_result.get("type") != "auth_ok":
                raise HomeAssistantClientError(f"WebSocket authentication failed: {auth_result}")

            # Restore the caller-supplied timeout for the command response.
            ws.sock.settimeout(timeout)  # type: ignore[union-attr]

            # Send command and receive response
            ws.send(json.dumps(payload))
            response: dict[str, Any] = json.loads(ws.recv())
            return response
        except websocket.WebSocketTimeoutException as e:
            raise HomeAssistantTimeoutError(f"Home Assistant request timed out: WebSocket error communicating with Home Assistant at {ws_url}: {e}")
        except websocket.WebSocketException as e:
            raise HomeAssistantClientError(f"WebSocket error communicating with Home Assistant at {ws_url}: {e}")
        finally:
            ws.close()

    def _get_entity_config(self, entity_id: str) -> dict[str, Any]:
        """Fetch the current entity registry config (labels and area_id) for an entity.

        Uses the WebSocket ``config/entity_registry/get`` command to retrieve the
        current labels and area assignment for an entity in a single round-trip.

        Args:
            entity_id: The entity ID to query (e.g., 'light.living_room').

        Returns:
            A dict with keys ``"labels"`` (list[str]) and ``"area_id"`` (Optional[str]).

        Raises:
            HomeAssistantClientError: If the entity registry cannot be read.
        """
        response = self._ws_send_receive({"id": 1, "type": "config/entity_registry/get", "entity_id": entity_id})
        # id=1 is safe: _ws_send_receive opens a fresh connection per call, so there is no ID collision.
        if not response.get("success"):
            raise HomeAssistantClientError(f"Failed to get entity registry config for {entity_id}: {response}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise HomeAssistantClientError(f"Failed to get entity registry config for {entity_id}: unexpected result payload: {response}")
        raw_labels = result.get("labels", [])
        labels = [] if raw_labels is None else raw_labels
        return {
            "labels": labels,
            "area_id": result.get("area_id"),
        }

    def _update_entity_registry(self, entity_id: str, area: Optional[str] = _UNSET, labels: Optional[list[str]] = _UNSET) -> None:
        """Send a single entity-registry update containing only the specified fields.

        Builds a ``config/entity_registry/update`` payload from the supplied arguments,
        including only the fields that were explicitly provided (i.e. not the sentinel).
        Both fields may be supplied together, resulting in a single atomic round-trip.

        Args:
            entity_id: The entity ID to update (e.g., 'light.living_room').
            area: The area ID to assign, or ``None`` to remove the area assignment.
                Omit to leave the area field out of the payload entirely.
            labels: The complete list of label IDs to assign (``None`` is normalised to
                ``[]``). Omit to leave the labels field out of the payload entirely.

        Raises:
            HomeAssistantClientError: If the entity registry update fails.
        """
        payload: dict[str, Any] = {"id": 1, "type": "config/entity_registry/update", "entity_id": entity_id}
        # id=1 is safe: _ws_send_receive opens a fresh connection per call, so there is no ID collision.
        if area is not _UNSET:
            payload["area_id"] = area
        if labels is not _UNSET:
            payload["labels"] = labels if labels is not None else []
        response = self._ws_send_receive(payload)
        if not response.get("success"):
            raise HomeAssistantClientError(f"Failed to update entity registry for {entity_id}: {response}")

    def _ensure_area_exists(self, area_id: str) -> None:
        """Ensure an area with the given ID exists in the area registry, creating it if necessary.

        The known area IDs are fetched from the registry on the first call and cached on the
        instance for the lifetime of the session. Subsequent calls skip the list round-trip
        entirely when the area is already known. New areas are added to the cache after
        successful creation so that later calls for the same ID are also free of network overhead.

        Args:
            area_id: The area ID to check and, if absent, create (e.g., ``'living_room'``).

        Raises:
            HomeAssistantClientError: If listing or creating the area fails.
        """
        if self._known_area_ids is None:
            list_response = self._ws_send_receive({"id": 1, "type": "config/area_registry/list"})
            # id=1 is safe: _ws_send_receive opens a fresh connection per call, so there is no ID collision.
            if not list_response.get("success"):
                raise HomeAssistantClientError(f"Failed to list area registry: {list_response}")
            self._known_area_ids = {entry["area_id"] for entry in (list_response.get("result") or [])}
        if area_id not in self._known_area_ids:
            create_response = self._ws_send_receive({"id": 1, "type": "config/area_registry/create", "name": area_id})
            if not create_response.get("success"):
                raise HomeAssistantClientError(f"Failed to create area '{area_id}': {create_response}")
            self._known_area_ids.add(area_id)

    def _ensure_labels_exist(self, label_ids: list[str]) -> None:
        """Ensure all given label IDs exist in the label registry, creating any that are missing.

        The known label IDs are fetched from the registry on the first call and cached on the
        instance for the lifetime of the session. Subsequent calls skip the list round-trip
        entirely when all requested labels are already known. New labels are added to the cache
        after successful creation so that later calls for the same IDs are also free of network
        overhead. Duplicate IDs within ``label_ids`` are silently de-duplicated.

        Args:
            label_ids: The label IDs to check and, if absent, create (e.g., ``['morning', 'night_mode']``).

        Raises:
            HomeAssistantClientError: If listing or creating labels fails.
        """
        if not label_ids:
            return
        if self._known_label_ids is None:
            list_response = self._ws_send_receive({"id": 1, "type": "config/label_registry/list"})
            # id=1 is safe: _ws_send_receive opens a fresh connection per call, so there is no ID collision.
            if not list_response.get("success"):
                raise HomeAssistantClientError(f"Failed to list label registry: {list_response}")
            self._known_label_ids = {entry["label_id"] for entry in (list_response.get("result") or [])}
        for label_id in dict.fromkeys(label_ids):
            if label_id not in self._known_label_ids:
                create_response = self._ws_send_receive({"id": 1, "type": "config/label_registry/create", "name": label_id})
                if not create_response.get("success"):
                    raise HomeAssistantClientError(f"Failed to create label '{label_id}': {create_response}")
                self._known_label_ids.add(label_id)

    def given_entity_has(
        self,
        entity_id: str,
        area: Optional[str] = _UNSET,
        labels: Optional[list[str]] = _UNSET,
    ) -> None:
        """Assign an area and/or labels to an entity for testing purposes, with automatic rollback.

        Saves the entity's current area and labels before any modification so they can be
        restored at the end of the test by ``restore_entity_config()``. If called multiple
        times for the same ``entity_id`` during a test, only the config captured on the
        first call is saved (preserving the pre-test state regardless of subsequent updates).

        At least one of ``area`` or ``labels`` must be provided (i.e. not left as the
        default sentinel). The update is sent as a single WebSocket call — only the fields
        explicitly provided are included in the payload, leaving omitted fields unchanged.

        If the specified area or any of the specified labels do not yet exist in the
        Home Assistant registries, they are created automatically before the entity
        registry update is applied. Areas and labels created this way are **not** removed
        at the end of the test — they persist for the remainder of the test session.

        Args:
            entity_id: The entity ID to update (e.g., ``'light.living_room'``). Must be
                an entity registered in the HA entity registry.
            area: The area ID to assign (e.g., ``'living_room'``), ``None`` to remove the
                entity from its current area, or omit entirely to leave the area unchanged.
                If the area does not exist in the area registry it is created automatically.
            labels: The complete list of label IDs to assign (e.g., ``['night_mode']``),
                ``None`` to remove all labels, or omit entirely to leave labels unchanged.
                Any label IDs that do not exist in the label registry are created automatically.

        Raises:
            ValueError: If neither ``area`` nor ``labels`` is provided.
            HomeAssistantClientError: If the entity registry cannot be read or updated, or
                if creating a missing area or label fails.

        Examples:
            Set area only::

                home_assistant.given_entity_has("light.living_room", area="living_room")

            Set labels only::

                home_assistant.given_entity_has("light.living_room", labels=["night_mode"])

            Set both area and labels::

                home_assistant.given_entity_has("light.living_room", area="living_room", labels=["night_mode"])

            Remove area assignment::

                home_assistant.given_entity_has("light.living_room", area=None)

            Remove all labels::

                home_assistant.given_entity_has("light.living_room", labels=None)
        """
        if area is _UNSET and labels is _UNSET:
            raise ValueError("At least one of 'area' or 'labels' must be explicitly provided")

        if area is not _UNSET and area is not None:
            self._ensure_area_exists(area)
        if labels is not _UNSET and labels is not None:
            self._ensure_labels_exist(labels)

        if entity_id not in self._entity_original_config:
            self._entity_original_config[entity_id] = self._get_entity_config(entity_id)

        self._update_entity_registry(entity_id, area=area, labels=labels)

    def restore_entity_config(self) -> None:
        """Restore all entity labels and areas modified by given_entity_has() to their original values.

        This method is called automatically after each test function completes.
        It restores both labels and area for all entities modified via ``given_entity_has()``.
        Successfully restored entities are cleared from tracking immediately, while
        failed restorations remain tracked.

        Raises:
            HomeAssistantClientError: If any config restoration fails.
        """
        errors = []
        successfully_restored = []

        for entity_id, original_config in list(self._entity_original_config.items()):
            try:
                # Re-entering given_entity_has() here is safe: the snapshot guard
                # ("if entity_id not in self._entity_original_config") is still False
                # for each entity_id because we have not yet deleted entries from
                # _entity_original_config (that happens in the loop below, only after
                # success).  So the pre-test config is not overwritten by the restore call.
                self.given_entity_has(entity_id, area=original_config["area_id"], labels=original_config["labels"])
                successfully_restored.append(entity_id)
            except HomeAssistantClientError as e:
                errors.append(str(e))

        for entity_id in successfully_restored:
            del self._entity_original_config[entity_id]

        if errors:
            raise HomeAssistantClientError(f"Failed to restore config for {len(errors)} entities:\n" + "\n".join(errors))

    def _freeze_template_entity(self, entity_id: str) -> None:
        """Freeze a template entity to prevent re-evaluation from overwriting state overrides.

        Sends a WebSocket command to the ha_test_harness integration to add the entity
        to the frozen set. The monkey-patched TemplateEntity._handle_results checks this
        set and skips re-evaluation for frozen entities. Idempotent.
        """
        payload: dict[str, Any] = {"id": 1, "type": "ha_test_harness/template/freeze", "entity_id": entity_id}
        response = self._ws_send_receive(payload)
        if not response.get("success"):
            raise HomeAssistantClientError(f"Failed to freeze template entity {entity_id}: {response}")
        self._frozen_template_entities.add(entity_id)

    def _unfreeze_template_entity(self, entity_id: str) -> None:
        """Unfreeze a template entity to restore normal template re-evaluation."""
        payload: dict[str, Any] = {"id": 1, "type": "ha_test_harness/template/unfreeze", "entity_id": entity_id}
        response = self._ws_send_receive(payload)
        if not response.get("success"):
            raise HomeAssistantClientError(f"Failed to unfreeze template entity {entity_id}: {response}")
        self._frozen_template_entities.discard(entity_id)

    def restore_entity_states(self) -> None:
        """Restore all entity states modified by set_state() to their original values.

        This method is called automatically after each test function completes.
        It restores both state and attributes for all entities modified via ``set_state()``.
        If an entity didn't exist before ``set_state()`` was called (snapshot is None),
        it is removed. Tracking is cleared regardless of success or failure to prevent
        state pollution across tests.

        Frozen template entities are unfrozen before state restoration to allow normal
        template re-evaluation to resume.

        Raises:
            HomeAssistantClientError: If any state restoration fails.
        """
        frozen_entities = list(self._frozen_template_entities)
        self._frozen_template_entities.clear()
        for entity_id in frozen_entities:
            self._unfreeze_template_entity(entity_id)

        errors = []

        for entity_id, original_state in list(self._entity_original_state.items()):
            try:
                if original_state is None:
                    self.remove_entity(entity_id)
                else:
                    state_value = original_state.get("state", "")
                    attributes_value = original_state.get("attributes")
                    self._apply_state(entity_id, state_value, attributes_value, _freeze=False)
            except HomeAssistantClientError as e:
                errors.append(str(e))

        self._entity_original_state.clear()

        if errors:
            raise HomeAssistantClientError(f"Failed to restore state for {len(errors)} entities:\n" + "\n".join(errors))

    def clean_up_test_entities(self) -> None:
        """Remove all entities created via given_an_entity().

        This method is called automatically after each test function completes.
        It removes all tracked test entities. Successfully removed entities are
        cleared from tracking immediately, while failed removals remain tracked
        for potential retry.

        Raises:
            HomeAssistantClientError: If any entity removal fails.
        """
        errors = []
        successfully_removed = []

        for entity_id in list(self._created_entities):
            try:
                self.remove_entity(entity_id)
                successfully_removed.append(entity_id)
            except HomeAssistantClientError as e:
                errors.append(str(e))

        # Remove only successfully deleted entities from tracking
        for entity_id in successfully_removed:
            self._created_entities.discard(entity_id)

        # Raise if there were any errors
        if errors:
            raise HomeAssistantClientError(f"Failed to clean up {len(errors)} test entities:\n" + "\n".join(errors))
