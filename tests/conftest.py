"""
Stub out homeassistant modules so coordinator tests run without HA installed.
Must be imported before any module that touches homeassistant at import time.
"""

import asyncio
import sys
import types
from datetime import timedelta


# ---------------------------------------------------------------------------
# Minimal stubs
# ---------------------------------------------------------------------------

class UpdateFailed(Exception):
    """Mirrors homeassistant.helpers.update_coordinator.UpdateFailed."""


class DataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator."""

    def __init__(self, hass, logger, *, name: str, update_interval: timedelta) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = None

    async def _async_update_data(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Register stubs before any component module is imported
# ---------------------------------------------------------------------------

def _register_stubs() -> None:
    ha = types.ModuleType("homeassistant")
    ha_core = types.ModuleType("homeassistant.core")
    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_coord = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_coord.UpdateFailed = UpdateFailed
    ha_coord.DataUpdateCoordinator = DataUpdateCoordinator

    sys.modules.setdefault("homeassistant", ha)
    sys.modules.setdefault("homeassistant.core", ha_core)
    sys.modules.setdefault("homeassistant.helpers", ha_helpers)
    sys.modules.setdefault("homeassistant.helpers.update_coordinator", ha_coord)


_register_stubs()
