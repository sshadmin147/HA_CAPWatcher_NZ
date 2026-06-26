"""
Stub out homeassistant modules so tests run without HA installed.
Must execute before any module that touches homeassistant at import time.
"""

import sys
import types
from datetime import timedelta


# ---------------------------------------------------------------------------
# Minimal HA stubs
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
        self.last_update_success = True
        self._listeners: list = []

    async def _async_update_data(self):
        raise NotImplementedError

    def async_add_listener(self, callback):
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)


class CoordinatorEntity:
    """Minimal stand-in for CoordinatorEntity."""

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self.hass = getattr(coordinator, "hass", None)

    async def async_remove(self) -> None:
        pass

    async def async_write_ha_state(self) -> None:
        pass


def callback(func):
    """Passthrough decorator — real HA uses this to mark callbacks."""
    return func


# ---------------------------------------------------------------------------
# Register stubs before any component module is imported
# ---------------------------------------------------------------------------

def _register_stubs() -> None:
    ha = types.ModuleType("homeassistant")
    ha_core = types.ModuleType("homeassistant.core")
    ha_core.callback = callback

    ha_helpers = types.ModuleType("homeassistant.helpers")
    ha_helpers_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    ha_components = types.ModuleType("homeassistant.components")
    ha_components_sensor = types.ModuleType("homeassistant.components.sensor")

    ha_coord = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_coord.UpdateFailed = UpdateFailed
    ha_coord.DataUpdateCoordinator = DataUpdateCoordinator
    ha_coord.CoordinatorEntity = CoordinatorEntity

    sys.modules.setdefault("homeassistant", ha)
    sys.modules.setdefault("homeassistant.core", ha_core)
    sys.modules.setdefault("homeassistant.helpers", ha_helpers)
    sys.modules.setdefault("homeassistant.helpers.update_coordinator", ha_coord)
    sys.modules.setdefault("homeassistant.helpers.entity_platform", ha_helpers_ep)
    sys.modules.setdefault("homeassistant.components", ha_components)
    sys.modules.setdefault("homeassistant.components.sensor", ha_components_sensor)
    sys.modules.setdefault("homeassistant.config_entries", types.ModuleType("homeassistant.config_entries"))


_register_stubs()
