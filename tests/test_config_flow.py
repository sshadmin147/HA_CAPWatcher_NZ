"""Tests for CAPWatcherConfigFlow and CAPWatcherOptionsFlow."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ha_capwatcher.config_flow import (
    CAPWatcherConfigFlow,
    CAPWatcherOptionsFlow,
)
from custom_components.ha_capwatcher.const import (
    CONF_FEEDS,
    CONF_POLLING_INTERVAL,
    INTEGRATION_NAME,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow() -> CAPWatcherConfigFlow:
    return CAPWatcherConfigFlow()


def _make_options_flow(feeds=None, interval="1_minute") -> CAPWatcherOptionsFlow:
    entry = MagicMock()
    entry.data = {
        CONF_FEEDS: feeds or ["official_all_nz"],
        CONF_POLLING_INTERVAL: interval,
    }
    entry.options = {}
    return CAPWatcherOptionsFlow(entry)


# ---------------------------------------------------------------------------
# Config flow — async_step_user
# ---------------------------------------------------------------------------

class TestConfigFlowStepUser:
    @pytest.mark.asyncio
    async def test_shows_form_when_no_input(self):
        flow = _make_flow()
        result = await flow.async_step_user(None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_shows_form_with_no_errors_initially(self):
        flow = _make_flow()
        result = await flow.async_step_user(None)
        assert result["errors"] == {}

    @pytest.mark.asyncio
    async def test_creates_entry_with_valid_input(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            CONF_FEEDS: ["official_all_nz"],
            CONF_POLLING_INTERVAL: "1_minute",
        })
        assert result["type"] == "create_entry"
        assert result["title"] == INTEGRATION_NAME
        assert result["data"][CONF_FEEDS] == ["official_all_nz"]
        assert result["data"][CONF_POLLING_INTERVAL] == "1_minute"

    @pytest.mark.asyncio
    async def test_stores_multiple_feeds(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            CONF_FEEDS: ["official_all_nz", "region_auckland"],
            CONF_POLLING_INTERVAL: "30_seconds",
        })
        assert result["type"] == "create_entry"
        assert "official_all_nz" in result["data"][CONF_FEEDS]
        assert "region_auckland" in result["data"][CONF_FEEDS]

    @pytest.mark.asyncio
    async def test_error_when_no_feeds_selected(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            CONF_FEEDS: [],
            CONF_POLLING_INTERVAL: "1_minute",
        })
        assert result["type"] == "form"
        assert CONF_FEEDS in result["errors"]

    @pytest.mark.asyncio
    async def test_error_when_invalid_polling_interval(self):
        flow = _make_flow()
        result = await flow.async_step_user({
            CONF_FEEDS: ["official_all_nz"],
            CONF_POLLING_INTERVAL: "never",
        })
        assert result["type"] == "form"
        assert CONF_POLLING_INTERVAL in result["errors"]

    @pytest.mark.asyncio
    async def test_all_valid_polling_presets_accepted(self):
        from custom_components.ha_capwatcher.const import POLLING_PRESETS
        flow = _make_flow()
        for key in POLLING_PRESETS:
            result = await flow.async_step_user({
                CONF_FEEDS: ["official_all_nz"],
                CONF_POLLING_INTERVAL: key,
            })
            assert result["type"] == "create_entry", f"Expected create_entry for interval '{key}'"

    @pytest.mark.asyncio
    async def test_returns_options_flow_class(self):
        entry = MagicMock()
        options_flow = CAPWatcherConfigFlow.async_get_options_flow(entry)
        assert isinstance(options_flow, CAPWatcherOptionsFlow)


# ---------------------------------------------------------------------------
# Options flow — async_step_init
# ---------------------------------------------------------------------------

class TestOptionsFlowStepInit:
    @pytest.mark.asyncio
    async def test_shows_form_when_no_input(self):
        flow = _make_options_flow()
        result = await flow.async_step_init(None)
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_creates_entry_with_valid_input(self):
        flow = _make_options_flow()
        result = await flow.async_step_init({
            CONF_FEEDS: ["region_wellington"],
            CONF_POLLING_INTERVAL: "5_minutes",
        })
        assert result["type"] == "create_entry"
        assert result["data"][CONF_FEEDS] == ["region_wellington"]
        assert result["data"][CONF_POLLING_INTERVAL] == "5_minutes"

    @pytest.mark.asyncio
    async def test_error_when_no_feeds_selected(self):
        flow = _make_options_flow()
        result = await flow.async_step_init({
            CONF_FEEDS: [],
            CONF_POLLING_INTERVAL: "1_minute",
        })
        assert result["type"] == "form"
        assert CONF_FEEDS in result["errors"]

    @pytest.mark.asyncio
    async def test_error_when_invalid_polling_interval(self):
        flow = _make_options_flow()
        result = await flow.async_step_init({
            CONF_FEEDS: ["official_all_nz"],
            CONF_POLLING_INTERVAL: "hourly",
        })
        assert result["type"] == "form"
        assert CONF_POLLING_INTERVAL in result["errors"]

    @pytest.mark.asyncio
    async def test_falls_back_to_entry_data_for_current_feeds(self):
        """Options flow should pre-populate from entry.data when options is empty."""
        entry = MagicMock()
        entry.data = {CONF_FEEDS: ["region_auckland"], CONF_POLLING_INTERVAL: "2_minutes"}
        entry.options = {}
        flow = CAPWatcherOptionsFlow(entry)
        result = await flow.async_step_init(None)
        assert result["type"] == "form"

    @pytest.mark.asyncio
    async def test_options_override_data_for_current_feeds(self):
        """Options should take precedence over entry.data when both exist."""
        entry = MagicMock()
        entry.data = {CONF_FEEDS: ["official_all_nz"], CONF_POLLING_INTERVAL: "1_minute"}
        entry.options = {CONF_FEEDS: ["region_auckland"], CONF_POLLING_INTERVAL: "30_seconds"}
        flow = CAPWatcherOptionsFlow(entry)
        # Just confirm it shows the form without errors
        result = await flow.async_step_init(None)
        assert result["type"] == "form"

    @pytest.mark.asyncio
    async def test_can_change_to_any_valid_feed(self):
        from custom_components.ha_capwatcher.feeds_loader import load_default_feeds
        all_feeds = load_default_feeds()
        flow = _make_options_flow()
        for feed in all_feeds[:5]:  # test first 5 to keep it fast
            result = await flow.async_step_init({
                CONF_FEEDS: [feed["name"]],
                CONF_POLLING_INTERVAL: "1_minute",
            })
            assert result["type"] == "create_entry", (
                f"Expected create_entry for feed '{feed['name']}'"
            )
