"""
Stub out homeassistant modules so tests run without HA installed.
Must execute before any module that touches homeassistant at import time.
"""

import sys
import types
from datetime import timedelta


# ---------------------------------------------------------------------------
# Entity hierarchy stubs
# ---------------------------------------------------------------------------

class Entity:
    """Minimal stub for homeassistant.helpers.entity.Entity."""

    _attr_should_poll = False
    _attr_icon = None
    _attr_native_unit_of_measurement = None

    def __init__(self) -> None:
        self._remove_callbacks: list = []

    def async_on_remove(self, callback) -> None:
        self._remove_callbacks.append(callback)

    async def async_write_ha_state(self) -> None:
        pass

    async def async_added_to_hass(self) -> None:
        pass

    async def async_remove(self) -> None:
        pass


class CoordinatorEntity(Entity):
    """Minimal stub for homeassistant.helpers.update_coordinator.CoordinatorEntity."""

    def __init__(self, coordinator) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.hass = getattr(coordinator, "hass", None)


# ---------------------------------------------------------------------------
# Coordinator stubs
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

    async def async_config_entry_first_refresh(self) -> None:
        self.data = await self._async_update_data()

    def async_add_listener(self, callback):
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        for cb in list(self._listeners):
            cb()


# ---------------------------------------------------------------------------
# Config flow stubs
# ---------------------------------------------------------------------------

class ConfigFlow:
    """Minimal stub for homeassistant.config_entries.ConfigFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_create_entry(self, title: str, data: dict) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, step_id: str, data_schema=None, errors=None) -> dict:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_abort(self, reason: str) -> dict:
        return {"type": "abort", "reason": reason}


class OptionsFlow:
    """Minimal stub for homeassistant.config_entries.OptionsFlow."""

    def async_create_entry(self, title: str, data: dict) -> dict:
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, step_id: str, data_schema=None, errors=None) -> dict:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }


# ---------------------------------------------------------------------------
# Misc stubs
# ---------------------------------------------------------------------------

def callback(func):
    """Passthrough decorator — real HA uses this to mark callbacks."""
    return func


class _EntityRegistryStub:
    """Minimal stub for homeassistant.helpers.entity_registry.EntityRegistry."""

    def async_get_entity_id(self, domain: str, platform: str, unique_id: str):
        return None

    def async_remove(self, entity_id: str) -> None:
        pass


def entity_registry_async_get(hass):
    """Minimal stub for homeassistant.helpers.entity_registry.async_get."""
    return _EntityRegistryStub()


def entity_registry_async_entries_for_config_entry(registry, config_entry_id: str):
    """Minimal stub for homeassistant.helpers.entity_registry.async_entries_for_config_entry."""
    return []


class SelectSelectorConfig:
    """Minimal stub for homeassistant.helpers.selector.SelectSelectorConfig."""
    def __init__(self, options=None, multiple=False, **kwargs):
        self.options = options or []
        self.multiple = multiple


class SelectSelector:
    """Minimal stub for homeassistant.helpers.selector.SelectSelector."""
    def __init__(self, config: SelectSelectorConfig):
        self.config = config

    def __call__(self, value):
        return value


class _HassStub:
    """Minimal hass stub used inside config flow tests."""
    async def async_add_executor_job(self, fn, *args):
        return fn(*args)


# ---------------------------------------------------------------------------
# Register all stubs before any component module is imported
# ---------------------------------------------------------------------------

def _register_stubs() -> None:
    ha = types.ModuleType("homeassistant")

    ha_core = types.ModuleType("homeassistant.core")
    ha_core.callback = callback

    ha_helpers = types.ModuleType("homeassistant.helpers")

    ha_helpers_entity = types.ModuleType("homeassistant.helpers.entity")
    ha_helpers_entity.Entity = Entity

    ha_helpers_ep = types.ModuleType("homeassistant.helpers.entity_platform")

    ha_coord = types.ModuleType("homeassistant.helpers.update_coordinator")
    ha_coord.UpdateFailed = UpdateFailed
    ha_coord.DataUpdateCoordinator = DataUpdateCoordinator
    ha_coord.CoordinatorEntity = CoordinatorEntity

    ha_config_entries = types.ModuleType("homeassistant.config_entries")
    ha_config_entries.ConfigFlow = ConfigFlow
    ha_config_entries.OptionsFlow = OptionsFlow

    ha_components = types.ModuleType("homeassistant.components")
    ha_components_sensor = types.ModuleType("homeassistant.components.sensor")

    ha_selector = types.ModuleType("homeassistant.helpers.selector")
    ha_selector.SelectSelector = SelectSelector
    ha_selector.SelectSelectorConfig = SelectSelectorConfig

    ha_entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    ha_entity_registry.async_get = entity_registry_async_get
    ha_entity_registry.async_entries_for_config_entry = entity_registry_async_entries_for_config_entry

    for name, mod in [
        ("homeassistant", ha),
        ("homeassistant.core", ha_core),
        ("homeassistant.helpers", ha_helpers),
        ("homeassistant.helpers.entity", ha_helpers_entity),
        ("homeassistant.helpers.entity_platform", ha_helpers_ep),
        ("homeassistant.helpers.update_coordinator", ha_coord),
        ("homeassistant.helpers.selector", ha_selector),
        ("homeassistant.helpers.entity_registry", ha_entity_registry),
        ("homeassistant.config_entries", ha_config_entries),
        ("homeassistant.components", ha_components),
        ("homeassistant.components.sensor", ha_components_sensor),
    ]:
        sys.modules.setdefault(name, mod)

    # Patch flow stubs with a hass stub so async_add_executor_job works in tests
    ConfigFlow.hass = _HassStub()
    OptionsFlow.hass = _HassStub()


_register_stubs()
