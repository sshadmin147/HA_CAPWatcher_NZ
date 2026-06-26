"""HA-CAPWatcher integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_FEEDS, CONF_POLLING_INTERVAL, DOMAIN, POLLING_PRESETS
from .coordinator import CAPFeedCoordinator, RateLimitQueue
from .feeds_loader import load_default_feeds, merge_feeds, validate_feed

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


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
    all_feeds = load_default_feeds()
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload HA-CAPWatcher config entry and close HTTP session."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["session"].close()
    return unload_ok
