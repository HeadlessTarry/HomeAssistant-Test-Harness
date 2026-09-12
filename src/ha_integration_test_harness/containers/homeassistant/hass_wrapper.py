#!/usr/bin/env python3
"""Home Assistant wrapper with frozen time support.

Patches time.time() before HA loads to ensure all HA code uses fake time from the
beginning. Time stays exactly at the set value until explicitly changed by a test.

The wrapper:
- Captures real time at startup and freezes it
- Stores _frozen_time_value: float (Unix timestamp) as a module-level global
- Registers itself in sys.modules['hass_wrapper'] so the integration can import it
- Exposes get_fake_time(), set_fake_time(), is_frozen_time_mode() functions
"""

from __future__ import annotations

import sys
import time

_frozen_time_value: float = time.time()
_frozen_time_mode: bool = True


def get_fake_time() -> float:
    """Return the current frozen time value."""
    return _frozen_time_value


def set_fake_time(timestamp: float) -> None:
    """Set the frozen time to a new value."""
    global _frozen_time_value
    _frozen_time_value = timestamp


def is_frozen_time_mode() -> bool:
    """Return whether frozen time mode is active."""
    return _frozen_time_mode


def _patched_time() -> float:
    """Patched time.time() that returns frozen time."""
    return get_fake_time()


time.time = _patched_time


sys.modules["hass_wrapper"] = sys.modules[__name__]

if __name__ == "__main__":
    import runpy

    sys.argv = ["hass"] + sys.argv[1:]
    runpy.run_module("homeassistant", run_name="__main__", alter_sys=True)
