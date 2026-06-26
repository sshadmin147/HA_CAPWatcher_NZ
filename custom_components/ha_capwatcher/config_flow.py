"""Config flow for HA-CAPWatcher."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import (
    CONF_FEEDS,
    CONF_POLLING_INTERVAL,
    DOMAIN,
    INTEGRATION_NAME,
    POLLING_PRESETS,
)
from .feeds_loader import load_default_feeds, validate_feed

if TYPE_CHECKING:
    pass

PLATFORMS = ["sensor"]

_INTERVAL_LABELS = {
    "15_seconds": "15 seconds",
    "30_seconds": "30 seconds",
    "45_seconds": "45 seconds",
    "1_minute": "1 minute",
    "2_minutes": "2 minutes",
    "5_minutes": "5 minutes",
}


def _feed_schema(all_feeds: list[dict], current_feeds: list[str], current_interval: str) -> vol.Schema:
    """Build the voluptuous schema for the feed selection form."""
    feed_options = [
        {"value": f["name"], "label": f.get("label", f["name"])}
        for f in all_feeds
        if validate_feed(f) == []
    ]
    interval_options = [
        {"value": k, "label": _INTERVAL_LABELS.get(k, k)}
        for k in POLLING_PRESETS
    ]
    return vol.Schema({
        vol.Required(CONF_FEEDS, default=current_feeds): SelectSelector(
            SelectSelectorConfig(options=feed_options, multiple=True)
        ),
        vol.Required(CONF_POLLING_INTERVAL, default=current_interval): SelectSelector(
            SelectSelectorConfig(options=interval_options, multiple=False)
        ),
    })


class CAPWatcherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow for HA-CAPWatcher."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        all_feeds = await self.hass.async_add_executor_job(load_default_feeds)
        default_enabled = [f["name"] for f in all_feeds if f.get("enabled")]

        if user_input is not None:
            enabled = user_input.get(CONF_FEEDS, [])
            interval = user_input.get(CONF_POLLING_INTERVAL, "1_minute")

            if not enabled:
                errors[CONF_FEEDS] = "no_feeds_selected"
            elif interval not in POLLING_PRESETS:
                errors[CONF_POLLING_INTERVAL] = "invalid_polling_interval"
            else:
                return self.async_create_entry(
                    title=INTEGRATION_NAME,
                    data={
                        CONF_FEEDS: enabled,
                        CONF_POLLING_INTERVAL: interval,
                    },
                )

        schema = _feed_schema(all_feeds, default_enabled, "1_minute")
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> CAPWatcherOptionsFlow:
        return CAPWatcherOptionsFlow(config_entry)


class CAPWatcherOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for an existing HA-CAPWatcher entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        all_feeds = await self.hass.async_add_executor_job(load_default_feeds)

        current_feeds = (
            self._entry.options.get(CONF_FEEDS)
            or self._entry.data.get(CONF_FEEDS, [])
        )
        current_interval = (
            self._entry.options.get(CONF_POLLING_INTERVAL)
            or self._entry.data.get(CONF_POLLING_INTERVAL, "1_minute")
        )

        if user_input is not None:
            enabled = user_input.get(CONF_FEEDS, [])
            interval = user_input.get(CONF_POLLING_INTERVAL, "1_minute")

            if not enabled:
                errors[CONF_FEEDS] = "no_feeds_selected"
            elif interval not in POLLING_PRESETS:
                errors[CONF_POLLING_INTERVAL] = "invalid_polling_interval"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_FEEDS: enabled,
                        CONF_POLLING_INTERVAL: interval,
                    },
                )

        schema = _feed_schema(all_feeds, current_feeds, current_interval)
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
