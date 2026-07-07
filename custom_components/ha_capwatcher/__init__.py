"""HA-CAPWatcher integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_FEEDS, CONF_POLLING_INTERVAL, DOMAIN, POLLING_PRESETS
from .coordinator import CAPFeedCoordinator, RateLimitQueue
from .feeds_loader import load_default_feeds, merge_feeds, validate_feed

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "event"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA-CAPWatcher from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Resolve active feeds — options override initial data
    enabled_names: set[str] = set(
        entry.options.get(CONF_FEEDS) or entry.data.get(CONF_FEEDS, [])
    )
    polling_key: str = (
        entry.options.get(CONF_POLLING_INTERVAL)
        or entry.data.get(CONF_POLLING_INTERVAL, "1_minute")
    )
    poll_seconds: int = POLLING_PRESETS.get(polling_key, 60)

    # Load default feeds and merge with any custom feeds stored in options
    all_feeds = await hass.async_add_executor_job(load_default_feeds)
    custom_feeds = entry.options.get("custom_feeds", [])
    merged = merge_feeds(all_feeds, custom_feeds)

    active = [
        f for f in merged
        if f.get("name") in enabled_names and validate_feed(f) == []
    ]
    if not active:
        _LOGGER.warning("[%s] No valid enabled feeds — check configuration", DOMAIN)

    session = aiohttp.ClientSession()
    rate_queue = RateLimitQueue()
    coordinators: dict[str, CAPFeedCoordinator] = {}

    for feed in active:
        coord = CAPFeedCoordinator(
            hass=hass,
            feed_name=feed["name"],
            feed_url=feed["url"],
            poll_interval=poll_seconds,
            session=session,
            rate_queue=rate_queue,
        )
        try:
            await coord.async_config_entry_first_refresh()
        except UpdateFailed as exc:
            _LOGGER.warning("[%s] Initial poll failed for '%s': %s", DOMAIN, feed["name"], exc)
        coordinators[feed["name"]] = coord

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinators": coordinators,
        "session": session,
    }

    _cleanup_stale_alert_entities(hass, entry, coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _cleanup_stale_alert_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinators: dict[str, CAPFeedCoordinator],
) -> None:
    """Purge leftover per-alert sensor registry entries from past sessions.

    A per-alert sensor removes its own registry entry when its alert expires
    (see sensor.py), but only for alerts that expire while this integration
    is loaded. Alerts that already expired in an earlier session — including
    everything from before this cleanup existed — are left stranded as
    permanent 'unavailable' entities, so sweep them here on every setup.
    """
    registry = er.async_get(hass)
    sensor_entries = {
        reg_entry.unique_id: reg_entry.entity_id
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id)
        if reg_entry.domain == "sensor"
    }

    # Longest feed name first, so e.g. "region_auckland_enhanced" is matched
    # before the shorter "region_auckland" for a unique_id that belongs to it.
    feeds_longest_first = sorted(
        coordinators.values(), key=lambda c: len(c.feed_name), reverse=True
    )

    for unique_id, entity_id in sensor_entries.items():
        for coord in feeds_longest_first:
            prefix = f"{DOMAIN}_{coord.feed_name}_"
            if not unique_id.startswith(prefix):
                continue
            if coord.data is None:
                # First refresh failed — can't confirm this feed's alerts,
                # so don't risk deleting one that's still active.
                break
            if unique_id not in {f"{prefix}{aid}" for aid in coord.data.alerts}:
                registry.async_remove(entity_id)
            break


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA-CAPWatcher config entry and close HTTP session."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["session"].close()
    return unload_ok
