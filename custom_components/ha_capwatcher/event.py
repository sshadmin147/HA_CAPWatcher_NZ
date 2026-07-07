"""Event platform for HA-CAPWatcher — fires when alerts arrive or expire."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from .const import DOMAIN
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
    """Set up one CAPAlertEventEntity per configured feed."""
    coordinators: dict[str, CAPFeedCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    async_add_entities([
        CAPAlertEventEntity(coord) for coord in coordinators.values()
    ])


class CAPAlertEventEntity(EventEntity):
    """
    Stable event entity for a single CAP feed.

    Fires 'alert_new' when a previously unseen alert appears in the feed,
    and 'alert_expired' when one drops out. Both are selectable in the
    HA automation UI without any YAML.

    Event data for alert_new:
        severity, urgency, headline, area, feed, alert_id, cap_url

    Event data for alert_expired:
        feed, alert_id
    """

    _attr_event_types = ["alert_new", "alert_expired"]
    _attr_should_poll = False
    _attr_icon = "mdi:bell-alert"

    def __init__(self, coordinator: CAPFeedCoordinator) -> None:
        self._coordinator = coordinator
        self._known_ids: set[str] = set()

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._coordinator.feed_name}_events"

    @property
    def name(self) -> str:
        return f"{self._coordinator.feed_name} Alert Events"

    async def async_added_to_hass(self) -> None:
        # Seed known IDs from current data so we don't fire for alerts
        # that were already active when HA started.
        if self._coordinator.data:
            self._known_ids = set(self._coordinator.data.alerts)

        self.async_on_remove(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._coordinator.data is None:
            return

        current_ids = set(self._coordinator.data.alerts)
        alerts = self._coordinator.data.alerts

        for alert_id in current_ids - self._known_ids:
            alert = alerts[alert_id]
            self._trigger_event("alert_new", {
                "severity": alert.severity,
                "urgency": alert.urgency,
                "headline": alert.headline,
                "area": alert.area,
                "feed": self._coordinator.feed_name,
                "alert_id": alert_id,
                "cap_url": alert.cap_url,
            })
            _LOGGER.debug(
                "[%s] Fired alert_new: %s (%s)",
                self._coordinator.feed_name,
                alert.headline,
                alert.severity,
            )

        for alert_id in self._known_ids - current_ids:
            self._trigger_event("alert_expired", {
                "feed": self._coordinator.feed_name,
                "alert_id": alert_id,
            })
            _LOGGER.debug(
                "[%s] Fired alert_expired: %s",
                self._coordinator.feed_name,
                alert_id,
            )

        self._known_ids = current_ids
        self.async_write_ha_state()
