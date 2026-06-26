"""Tests for CAPFeedCoordinator and RateLimitQueue."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ha_capwatcher.coordinator import (
    CAPFeedCoordinator,
    FeedData,
    RateLimitQueue,
)

# --- Minimal Atom + CAP fixtures ---

ATOM_TWO_ALERTS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Severe Wind Warning</title>
    <id>tag:alerts.sshadmin.dev,2024:00000001</id>
    <updated>2024-06-26T10:00:00Z</updated>
    <author><name>MetService</name></author>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/1"/>
  </entry>
  <entry>
    <title>Heavy Rain Watch</title>
    <id>tag:alerts.sshadmin.dev,2024:00000002</id>
    <updated>2024-06-26T10:00:00Z</updated>
    <author><name>MetService</name></author>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/2"/>
  </entry>
</feed>"""

ATOM_ONE_ALERT = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Severe Wind Warning</title>
    <id>tag:alerts.sshadmin.dev,2024:00000001</id>
    <updated>2024-06-26T10:00:00Z</updated>
    <author><name>MetService</name></author>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/1"/>
  </entry>
</feed>"""

ATOM_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""

CAP_SEVERE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <description>Strong winds expected.</description>
    <area><areaDesc>Auckland</areaDesc></area>
  </info>
</alert>"""

CAP_WATCH = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Future</urgency>
    <severity>Watch</severity>
    <certainty>Possible</certainty>
    <description>Heavy rain possible.</description>
    <area><areaDesc>Auckland</areaDesc></area>
  </info>
</alert>"""

CAP_MISSING_SEVERITY = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <certainty>Likely</certainty>
  </info>
</alert>"""


# --- Helpers ---

def _make_response(text: str, status: int = 200) -> AsyncMock:
    """Build a fake aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.headers = {}
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_coordinator(hass_mock, responses: list[tuple[str, int]]) -> CAPFeedCoordinator:
    """
    Build a coordinator with a mocked aiohttp session.

    responses: list of (body, status) tuples returned in order per get() call.
    """
    session = MagicMock()
    call_iter = iter(responses)

    def _get(url, **kwargs):
        body, status = next(call_iter)
        return _make_response(body, status)

    session.get = MagicMock(side_effect=_get)

    rate_queue = RateLimitQueue()
    return CAPFeedCoordinator(
        hass=hass_mock,
        feed_name="test_feed",
        feed_url="https://alerts.sshadmin.dev/cap/feeds/official/all-nz",
        poll_interval=60,
        session=session,
        rate_queue=rate_queue,
    )


@pytest.fixture
def hass_mock():
    hass = MagicMock()
    hass.data = {}
    return hass


# --- RateLimitQueue tests ---

class TestRateLimitQueue:
    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        q = RateLimitQueue(max_per_minute=5)
        for _ in range(5):
            await q.acquire()
        assert len(q._request_times) == 5

    @pytest.mark.asyncio
    async def test_blocks_when_limit_reached(self):
        q = RateLimitQueue(max_per_minute=2)

        # Seed two requests at the start of the window
        q._request_times = [time.monotonic() - 59.0, time.monotonic() - 58.0]

        start = time.monotonic()
        await q.acquire()
        elapsed = time.monotonic() - start

        # Should have waited ~1-2 seconds for the oldest to expire
        assert elapsed >= 0.5, f"Expected wait, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_evicts_old_timestamps(self):
        q = RateLimitQueue(max_per_minute=5)
        q._request_times = [time.monotonic() - 65.0]  # older than 60s window
        await q.acquire()
        # Old timestamp evicted, only new one remains
        assert len(q._request_times) == 1


# --- Coordinator tests ---

class TestCAPFeedCoordinator:
    @pytest.mark.asyncio
    async def test_first_poll_creates_alerts(self, hass_mock):
        # 1 Atom fetch + 2 CAP doc fetches
        coord = _make_coordinator(hass_mock, [
            (ATOM_TWO_ALERTS, 200),
            (CAP_SEVERE, 200),
            (CAP_WATCH, 200),
        ])
        data = await coord._poll()

        assert isinstance(data, FeedData)
        assert len(data.alerts) == 2
        assert not data.feed_offline

    @pytest.mark.asyncio
    async def test_second_poll_uses_cache(self, hass_mock):
        # First poll: 1 Atom + 2 CAP docs
        # Second poll: 1 Atom only (cache hit, no CAP doc re-fetch)
        coord = _make_coordinator(hass_mock, [
            (ATOM_TWO_ALERTS, 200),
            (CAP_SEVERE, 200),
            (CAP_WATCH, 200),
            (ATOM_TWO_ALERTS, 200),  # second poll Atom only
        ])
        await coord._poll()
        data = await coord._poll()

        assert len(data.alerts) == 2
        # Session should have been called exactly 4 times (not 6)
        assert coord._session.get.call_count == 4

    @pytest.mark.asyncio
    async def test_evicts_expired_alert(self, hass_mock):
        # First poll: 2 alerts
        # Second poll: Atom only has 1 → second evicted
        coord = _make_coordinator(hass_mock, [
            (ATOM_TWO_ALERTS, 200),
            (CAP_SEVERE, 200),
            (CAP_WATCH, 200),
            (ATOM_ONE_ALERT, 200),
        ])
        await coord._poll()
        data = await coord._poll()

        assert len(data.alerts) == 1
        remaining = list(data.alerts.values())
        assert remaining[0].headline == "Severe Wind Warning"

    @pytest.mark.asyncio
    async def test_empty_feed_clears_all_alerts(self, hass_mock):
        coord = _make_coordinator(hass_mock, [
            (ATOM_TWO_ALERTS, 200),
            (CAP_SEVERE, 200),
            (CAP_WATCH, 200),
            (ATOM_EMPTY, 200),
        ])
        await coord._poll()
        data = await coord._poll()

        assert len(data.alerts) == 0

    @pytest.mark.asyncio
    async def test_skips_alert_with_missing_severity(self, hass_mock):
        cap_no_severity = CAP_MISSING_SEVERITY
        coord = _make_coordinator(hass_mock, [
            (ATOM_ONE_ALERT, 200),
            (cap_no_severity, 200),
        ])
        data = await coord._poll()

        # Alert skipped due to missing severity — not added to cache
        assert len(data.alerts) == 0

    @pytest.mark.asyncio
    async def test_raises_update_failed_on_http_error(self, hass_mock):
        coord = _make_coordinator(hass_mock, [
            ("", 500),
        ])
        with pytest.raises(UpdateFailed):
            await coord._poll()

    @pytest.mark.asyncio
    async def test_raises_update_failed_on_rate_limit(self, hass_mock):
        resp = AsyncMock()
        resp.status = 429
        resp.headers = {"Retry-After": "1"}
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=resp)

        coord = CAPFeedCoordinator(
            hass=hass_mock,
            feed_name="test",
            feed_url="https://example.com/feed",
            poll_interval=60,
            session=session,
            rate_queue=RateLimitQueue(),
        )
        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coord._poll()

    @pytest.mark.asyncio
    async def test_consecutive_errors_tracked(self, hass_mock):
        coord = _make_coordinator(hass_mock, [
            ("", 500),
            ("", 500),
            ("", 500),
            ("", 500),
            ("", 500),
        ])
        for _ in range(5):
            try:
                await coord._async_update_data()
            except UpdateFailed:
                pass

        assert coord._consecutive_errors == 5
        assert coord.is_feed_offline

    @pytest.mark.asyncio
    async def test_errors_reset_on_successful_poll(self, hass_mock):
        coord = _make_coordinator(hass_mock, [
            ("", 500),
            (ATOM_EMPTY, 200),
        ])
        try:
            await coord._async_update_data()
        except UpdateFailed:
            pass

        assert coord._consecutive_errors == 1

        await coord._async_update_data()
        assert coord._consecutive_errors == 0

    @pytest.mark.asyncio
    async def test_is_feed_offline_false_below_threshold(self, hass_mock):
        coord = _make_coordinator(hass_mock, [])
        coord._consecutive_errors = 4
        assert not coord.is_feed_offline

    @pytest.mark.asyncio
    async def test_active_alert_count(self, hass_mock):
        coord = _make_coordinator(hass_mock, [
            (ATOM_TWO_ALERTS, 200),
            (CAP_SEVERE, 200),
            (CAP_WATCH, 200),
        ])
        assert coord.active_alert_count == 0
        await coord._poll()
        assert coord.active_alert_count == 2

    @pytest.mark.asyncio
    async def test_alert_without_cap_url_skipped(self, hass_mock):
        atom_no_cap_url = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Alert Without CAP Link</title>
    <id>tag:alerts.sshadmin.dev,2024:99999</id>
    <updated>2024-06-26T10:00:00Z</updated>
  </entry>
</feed>"""
        coord = _make_coordinator(hass_mock, [(atom_no_cap_url, 200)])
        data = await coord._poll()
        assert len(data.alerts) == 0
