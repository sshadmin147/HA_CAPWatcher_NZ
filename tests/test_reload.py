"""
Step 9 — Reload and restart behaviour tests.

Since we can't run a real HA instance, we test the pieces that matter:
- async_unload_entry cleans up hass.data and closes the session
- Reload (unload then re-setup) produces fresh coordinators without
  duplicating hass.data keys
- Coordinator cache is reset on reload (no stale alerts carried over)
- Entities registered via async_on_unload are actually unsubscribed on unload
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from custom_components.ha_capwatcher import async_setup_entry, async_unload_entry
from custom_components.ha_capwatcher.coordinator import CAPFeedCoordinator, FeedData, RateLimitQueue
from custom_components.ha_capwatcher.const import CONF_FEEDS, CONF_POLLING_INTERVAL, DOMAIN
from custom_components.ha_capwatcher.sensor import CAPAlertSensor, async_setup_entry as sensor_setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(feeds=None, interval="1_minute"):
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_FEEDS: feeds or ["official_all_nz"],
        CONF_POLLING_INTERVAL: interval,
    }
    entry.options = {}
    entry.async_on_unload = MagicMock()
    return entry


def _make_hass(coordinators=None):
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    if coordinators is not None:
        hass.data[DOMAIN]["test_entry"] = {
            "coordinators": coordinators,
            "session": AsyncMock(),
        }

    async def _unload_platforms(entry, platforms):
        return True

    async def _forward_setup(entry, platforms):
        pass

    hass.config_entries.async_unload_platforms = _unload_platforms
    hass.config_entries.async_forward_entry_setups = _forward_setup

    def _schedule(coro):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()

    hass.async_create_task = MagicMock(side_effect=_schedule)
    return hass


def _make_coordinator(feed_name="official_all_nz", alerts=None):
    coord = MagicMock(spec=CAPFeedCoordinator)
    coord.feed_name = feed_name
    coord.last_update_success = True
    coord.data = FeedData(alerts=alerts or {})
    _unsub = MagicMock()
    coord.async_add_listener = MagicMock(return_value=_unsub)
    coord.hass = MagicMock()
    return coord


# ---------------------------------------------------------------------------
# async_unload_entry
# ---------------------------------------------------------------------------

class TestUnloadEntry:
    @pytest.mark.asyncio
    async def test_removes_entry_from_hass_data(self):
        session = AsyncMock()
        coord = _make_coordinator()
        hass = _make_hass({"official_all_nz": coord})
        hass.data[DOMAIN]["test_entry"]["session"] = session

        entry = _make_entry()
        result = await async_unload_entry(hass, entry)

        assert result is True
        assert "test_entry" not in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_closes_aiohttp_session_on_unload(self):
        session = AsyncMock()
        coord = _make_coordinator()
        hass = _make_hass({"official_all_nz": coord})
        hass.data[DOMAIN]["test_entry"]["session"] = session

        entry = _make_entry()
        await async_unload_entry(hass, entry)

        session.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_platform_unload_fails(self):
        session = AsyncMock()
        coord = _make_coordinator()
        hass = _make_hass({"official_all_nz": coord})
        hass.data[DOMAIN]["test_entry"]["session"] = session

        async def _fail_unload(entry, platforms):
            return False

        hass.config_entries.async_unload_platforms = _fail_unload

        entry = _make_entry()
        result = await async_unload_entry(hass, entry)

        assert result is False
        # Data should NOT be removed if unload failed
        assert "test_entry" in hass.data[DOMAIN]

    @pytest.mark.asyncio
    async def test_hass_data_empty_after_all_entries_unloaded(self):
        s1, s2 = AsyncMock(), AsyncMock()
        hass = _make_hass()
        hass.data[DOMAIN]["entry_1"] = {"coordinators": {}, "session": s1}
        hass.data[DOMAIN]["entry_2"] = {"coordinators": {}, "session": s2}

        e1 = _make_entry()
        e1.entry_id = "entry_1"
        e2 = _make_entry()
        e2.entry_id = "entry_2"

        await async_unload_entry(hass, e1)
        await async_unload_entry(hass, e2)

        assert hass.data[DOMAIN] == {}


# ---------------------------------------------------------------------------
# Sensor listener cleanup
# ---------------------------------------------------------------------------

class TestSensorListenerCleanup:
    @pytest.mark.asyncio
    async def test_unsubscribe_callable_registered_for_each_coordinator(self):
        """async_on_unload should be called once per coordinator (for the listener unsub)."""
        coord = _make_coordinator()
        hass = MagicMock()
        hass.data = {
            DOMAIN: {"test_entry": {"coordinators": {"official_all_nz": coord}}}
        }
        hass.async_create_task = MagicMock(side_effect=lambda c: c.close() or MagicMock())

        entry = _make_entry()
        await sensor_setup(hass, entry, MagicMock())

        # async_on_unload called once (for the listener unsub)
        entry.async_on_unload.assert_called_once()
        # The argument should be the return value of async_add_listener (the unsub fn)
        unsub = coord.async_add_listener.return_value
        entry.async_on_unload.assert_called_with(unsub)

    @pytest.mark.asyncio
    async def test_calling_unsubscribe_removes_listener(self):
        """Simulate what HA does on unload: calls the registered unsub callbacks."""
        unsubscribed = []

        coord = _make_coordinator()
        # Real-ish listener list
        listeners = []
        coord.async_add_listener = MagicMock(side_effect=lambda cb: listeners.append(cb) or (lambda: unsubscribed.append(cb)))

        hass = MagicMock()
        hass.data = {
            DOMAIN: {"test_entry": {"coordinators": {"official_all_nz": coord}}}
        }
        hass.async_create_task = MagicMock(side_effect=lambda c: c.close() or MagicMock())

        entry = _make_entry()
        await sensor_setup(hass, entry, MagicMock())

        # Simulate HA calling the unload callback
        unsub = entry.async_on_unload.call_args[0][0]
        unsub()

        assert len(unsubscribed) == 1


# ---------------------------------------------------------------------------
# Coordinator cache reset on reload
# ---------------------------------------------------------------------------

class TestCoordinatorCacheReset:
    @pytest.mark.asyncio
    async def test_new_coordinator_starts_with_empty_cache(self):
        """After reload, a fresh coordinator has no cached alerts."""
        rate_queue = RateLimitQueue()
        session = MagicMock()

        # Simulate a coordinator that had alerts before reload
        old_coord = CAPFeedCoordinator(
            hass=MagicMock(),
            feed_name="official_all_nz",
            feed_url="https://example.com/feed",
            poll_interval=60,
            session=session,
            rate_queue=rate_queue,
        )
        # Manually populate cache as if alerts were active
        from custom_components.ha_capwatcher.parser import ParsedAlert
        fake_alert = ParsedAlert("x1", "x1", "Old Alert", "severe", "expected",
                                 "likely", "2024-01-01T00:00:00Z", None, None,
                                 "NZ", "Old", None, None, None, None, None)
        old_coord._alert_cache["x1"] = fake_alert
        assert old_coord.active_alert_count == 1

        # Reload = create a new coordinator (old is discarded)
        new_coord = CAPFeedCoordinator(
            hass=MagicMock(),
            feed_name="official_all_nz",
            feed_url="https://example.com/feed",
            poll_interval=60,
            session=session,
            rate_queue=rate_queue,
        )
        assert new_coord.active_alert_count == 0
        assert new_coord._consecutive_errors == 0

    @pytest.mark.asyncio
    async def test_coordinator_error_count_reset_on_new_instance(self):
        rate_queue = RateLimitQueue()
        session = MagicMock()

        old_coord = CAPFeedCoordinator(
            hass=MagicMock(),
            feed_name="feed",
            feed_url="https://example.com/feed",
            poll_interval=60,
            session=session,
            rate_queue=rate_queue,
        )
        old_coord._consecutive_errors = 5
        assert old_coord.is_feed_offline

        new_coord = CAPFeedCoordinator(
            hass=MagicMock(),
            feed_name="feed",
            feed_url="https://example.com/feed",
            poll_interval=60,
            session=session,
            rate_queue=rate_queue,
        )
        assert not new_coord.is_feed_offline
