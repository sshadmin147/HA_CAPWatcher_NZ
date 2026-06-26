"""Sensor platform for HA-CAPWatcher — one entity per active CAP alert."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_AREA,
    ATTR_CAP_URL,
    ATTR_CATEGORY,
    ATTR_CERTAINTY,
    ATTR_DESCRIPTION,
    ATTR_EXPIRES,
    ATTR_FEED_NAME,
    ATTR_GEOMETRY,
    ATTR_HEADLINE,
    ATTR_INSTRUCTIONS,
    ATTR_ISSUED,
    ATTR_ONSET,
    ATTR_SOURCE,
    ATTR_URGENCY,
    DOMAIN,
    SEVERITY_COLORS,
)
from .coordinator import CAPFeedCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CAP alert sensor entities from a config entry."""
    coordinator: CAPFeedCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    tracked: dict[str, CAPAlertSensor] = {}

    @callback
    def _handle_update() -> None:
        if coordinator.data is None:
            return

        current_ids = set(coordinator.data.alerts)
        known_ids = set(tracked)

        new_entities: list[CAPAlertSensor] = []
        for alert_id in current_ids - known_ids:
            entity = CAPAlertSensor(coordinator, alert_id)
            tracked[alert_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

        for alert_id in known_ids - current_ids:
            entity = tracked.pop(alert_id)
            hass.async_create_task(entity.async_remove())

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))
    _handle_update()


class CAPAlertSensor(CoordinatorEntity):
    """
    A sensor entity representing a single active CAP alert.

    State is the severity string (extreme / severe / warning / watch / info).
    All CAP fields are exposed as extra_state_attributes.
    """

    _attr_icon = "mdi:alert"
    _attr_should_poll = False

    def __init__(self, coordinator: CAPFeedCoordinator, alert_id: str) -> None:
        super().__init__(coordinator)
        self._alert_id = alert_id

    # --- Core entity properties ---

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self.coordinator.feed_name}_{self._alert_id}"

    @property
    def name(self) -> str:
        alert = self._current_alert
        return alert.headline if alert else f"CAP Alert {self._alert_id}"

    @property
    def state(self) -> str | None:
        alert = self._current_alert
        return alert.severity if alert else None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._alert_id in self.coordinator.data.alerts
        )

    # --- Attributes ---

    @property
    def extra_state_attributes(self) -> dict:
        alert = self._current_alert
        if alert is None:
            return {}
        colors = SEVERITY_COLORS.get(alert.severity, {})
        return {
            ATTR_HEADLINE: alert.headline,
            ATTR_URGENCY: alert.urgency,
            ATTR_CERTAINTY: alert.certainty,
            ATTR_ISSUED: alert.issued,
            ATTR_EXPIRES: alert.expires,
            ATTR_ONSET: alert.onset,
            ATTR_AREA: alert.area,
            ATTR_DESCRIPTION: alert.description,
            ATTR_INSTRUCTIONS: alert.instructions,
            ATTR_CAP_URL: alert.cap_url,
            ATTR_SOURCE: alert.source,
            ATTR_CATEGORY: alert.category,
            ATTR_FEED_NAME: self.coordinator.feed_name,
            ATTR_GEOMETRY: alert.geometry_polygon,
            "severity_color": colors.get("hex"),
            "severity_background": colors.get("background"),
        }

    # --- Private helpers ---

    @property
    def _current_alert(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.alerts.get(self._alert_id)
