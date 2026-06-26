"""Sensor platform for HA-CAPWatcher."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
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
    ATTR_SEVERITY,
    ATTR_SOURCE,
    ATTR_URGENCY,
    DOMAIN,
    SEVERITIES,
    SEVERITY_COLORS,
)
from .coordinator import CAPFeedCoordinator
from .severity import get_highest_severity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all CAP alert sensor entities from a config entry."""
    coordinators: dict[str, CAPFeedCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]

    for coordinator in coordinators.values():
        _setup_feed_entities(hass, entry, coordinator, async_add_entities)

    # One set of aggregate helpers per config entry (across all feeds)
    coord_list = list(coordinators.values())
    async_add_entities([
        CAPAlertCountSensor(entry.entry_id, coord_list),
        CAPHighestSeveritySensor(entry.entry_id, coord_list),
        CAPLatestHeadlineSensor(entry.entry_id, coord_list),
    ])


def _setup_feed_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: CAPFeedCoordinator,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register per-alert entity tracking for one coordinator."""
    tracked: dict[str, CAPAlertSensor] = {}

    @callback
    def _handle_update(_coord: CAPFeedCoordinator = coordinator, _tracked: dict = tracked) -> None:
        if _coord.data is None:
            return

        current_ids = set(_coord.data.alerts)
        known_ids = set(_tracked)

        new_entities: list[CAPAlertSensor] = []
        for alert_id in current_ids - known_ids:
            entity = CAPAlertSensor(_coord, alert_id)
            _tracked[alert_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

        for alert_id in known_ids - current_ids:
            entity = _tracked.pop(alert_id)
            hass.async_create_task(entity.async_remove())

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))
    _handle_update()


# ---------------------------------------------------------------------------
# Per-alert entity
# ---------------------------------------------------------------------------

class CAPAlertSensor(CoordinatorEntity):
    """
    Sensor entity for a single active CAP alert.

    State = severity string (extreme / severe / warning / watch / info).
    All NZ-CAP fields are exposed as extra_state_attributes.
    """

    _attr_icon = "mdi:alert"
    _attr_should_poll = False

    def __init__(self, coordinator: CAPFeedCoordinator, alert_id: str) -> None:
        super().__init__(coordinator)
        self._alert_id = alert_id

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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    @property
    def _current_alert(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.alerts.get(self._alert_id)


# ---------------------------------------------------------------------------
# Aggregate helper entities (one set per config entry)
# ---------------------------------------------------------------------------

class _CAPAggregateEntity(Entity):
    """Base for entities that aggregate data across multiple coordinators."""

    _attr_should_poll = False

    def __init__(self, entry_id: str, coordinators: list[CAPFeedCoordinator]) -> None:
        super().__init__()
        self._entry_id = entry_id
        self._coordinators = coordinators

    async def async_added_to_hass(self) -> None:
        for coord in self._coordinators:
            self.async_on_remove(
                coord.async_add_listener(self.async_write_ha_state)
            )

    def _all_alerts(self) -> list:
        """Return all currently active alerts across every coordinator."""
        alerts = []
        for coord in self._coordinators:
            if coord.data:
                alerts.extend(coord.data.alerts.values())
        return alerts

    def _priority_alert(self):
        """Return the highest-severity alert, or None if no alerts are active."""
        alerts = self._all_alerts()
        if not alerts:
            return None
        for sev in SEVERITIES:
            for alert in alerts:
                if alert.severity == sev:
                    return alert
        return alerts[0]

    def _feed_for_alert(self, alert) -> str | None:
        """Return the feed name that owns the given alert."""
        for coord in self._coordinators:
            if coord.data and alert.alert_id in coord.data.alerts:
                return coord.feed_name
        return None


class CAPAlertCountSensor(_CAPAggregateEntity):
    """Total number of active alerts across all configured feeds."""

    _attr_icon = "mdi:bell-badge"
    _attr_native_unit_of_measurement = "alerts"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_alert_count"

    @property
    def name(self) -> str:
        return "Alert Count"

    @property
    def state(self) -> int:
        return len(self._all_alerts())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        breakdown: dict[str, int] = {}
        for coord in self._coordinators:
            if coord.data:
                breakdown[coord.feed_name] = len(coord.data.alerts)
        return {"by_feed": breakdown}


class CAPHighestSeveritySensor(_CAPAggregateEntity):
    """Highest severity currently active across all configured feeds."""

    _attr_icon = "mdi:alert-circle"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_highest_severity"

    @property
    def name(self) -> str:
        return "Highest Severity"

    @property
    def state(self) -> str:
        severities = [a.severity for a in self._all_alerts()]
        return get_highest_severity(severities)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        severity = self.state
        colors = SEVERITY_COLORS.get(severity, {})
        return {
            "severity_color": colors.get("hex"),
            "severity_background": colors.get("background"),
        }


class CAPLatestHeadlineSensor(_CAPAggregateEntity):
    """Headline of the highest-priority active alert across all feeds."""

    _attr_icon = "mdi:newspaper-variant"

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._entry_id}_latest_headline"

    @property
    def name(self) -> str:
        return "Latest Headline"

    @property
    def state(self) -> str | None:
        alert = self._priority_alert()
        return alert.headline if alert else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        alert = self._priority_alert()
        if alert is None:
            return {}
        return {
            ATTR_SEVERITY: alert.severity,
            ATTR_AREA: alert.area,
            ATTR_ISSUED: alert.issued,
            ATTR_FEED_NAME: self._feed_for_alert(alert),
        }
