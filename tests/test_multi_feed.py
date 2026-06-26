"""
Step 8 — Multi-feed integration tests.

Verifies that multiple coordinators running concurrently do not bleed alerts
between feeds, that the shared RateLimitQueue serialises all requests, and
that aggregate helpers correctly span all feeds.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ha_capwatcher.coordinator import (
    CAPFeedCoordinator,
    FeedData,
    RateLimitQueue,
)
from custom_components.ha_capwatcher.parser import ParsedAlert
from custom_components.ha_capwatcher.sensor import (
    CAPAlertCountSensor,
    CAPAlertSensor,
    CAPHighestSeveritySensor,
    CAPLatestHeadlineSensor,
    async_setup_entry,
)
from custom_components.ha_capwatcher.const import DOMAIN


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

ATOM_AUCKLAND = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Auckland Severe Wind</title>
    <id>tag:alerts.sshadmin.dev,2024:1001</id>
    <updated>2024-06-26T10:00:00Z</updated>
    <author><name>MetService</name></author>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/1001"/>
  </entry>
</feed>"""

ATOM_WELLINGTON = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Wellington Extreme Warning</title>
    <id>tag:alerts.sshadmin.dev,2024:2001</id>
    <updated>2024-06-26T11:00:00Z</updated>
    <author><name>MetService</name></author>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/2001"/>
  </entry>
</feed>"""

ATOM_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

CAP_SEVERE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <severity>Severe</severity>
    <urgency>Expected</urgency>
    <certainty>Likely</certainty>
    <description>Strong winds.</description>
    <area><areaDesc>Auckland</areaDesc></area>
  </info>
</alert>"""

CAP_EXTREME = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <severity>Extreme</severity>
    <urgency>Immediate</urgency>
    <certainty>Observed</certainty>
    <description>Extreme weather event.</description>
    <area><areaDesc>Wellington</areaDesc></area>
  </info>
</alert>"""


# ---------------------------------------------------------------------------
# Coordinator test helpers
# ---------------------------------------------------------------------------

def _make_response(body: str, status: int = 200):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=body)
    resp.headers = {}
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


def _make_coord(hass_mock, responses: list[tuple[str, int]], feed_name: str, feed_url: str, rate_queue: RateLimitQueue) -> CAPFeedCoordinator:
    session = MagicMock()
    call_iter = iter(responses)

    def _get(url, **kw):
        body, status = next(call_iter)
        return _make_response(body, status)

    session.get = MagicMock(side_effect=_get)
    return CAPFeedCoordinator(
        hass=hass_mock,
        feed_name=feed_name,
        feed_url=feed_url,
        poll_interval=60,
        session=session,
        rate_queue=rate_queue,
    )


@pytest.fixture
def hass_mock():
    hass = MagicMock()
    hass.data = {}
    return hass


# ---------------------------------------------------------------------------
# Feed isolation: alerts from one feed must not appear in another
# ---------------------------------------------------------------------------

class TestFeedIsolation:
    @pytest.mark.asyncio
    async def test_each_coordinator_tracks_its_own_alerts(self, hass_mock):
        rate_queue = RateLimitQueue()
        coord_a = _make_coord(hass_mock, [(ATOM_AUCKLAND, 200), (CAP_SEVERE, 200)], "auckland", "https://example.com/a", rate_queue)
        coord_b = _make_coord(hass_mock, [(ATOM_WELLINGTON, 200), (CAP_EXTREME, 200)], "wellington", "https://example.com/b", rate_queue)

        data_a = await coord_a._poll()
        data_b = await coord_b._poll()

        assert len(data_a.alerts) == 1
        assert len(data_b.alerts) == 1

        # IDs must be different
        ids_a = set(data_a.alerts.keys())
        ids_b = set(data_b.alerts.keys())
        assert ids_a.isdisjoint(ids_b), "Alert IDs overlap between feeds"

    @pytest.mark.asyncio
    async def test_alert_in_feed_a_not_visible_via_feed_b(self, hass_mock):
        rate_queue = RateLimitQueue()
        coord_a = _make_coord(hass_mock, [(ATOM_AUCKLAND, 200), (CAP_SEVERE, 200)], "auckland", "https://example.com/a", rate_queue)
        coord_b = _make_coord(hass_mock, [(ATOM_EMPTY, 200)], "wellington", "https://example.com/b", rate_queue)

        await coord_a._poll()
        data_b = await coord_b._poll()

        assert len(data_b.alerts) == 0, "Feed B should not see Feed A's alerts"

    @pytest.mark.asyncio
    async def test_expiry_in_one_feed_does_not_affect_other(self, hass_mock):
        rate_queue = RateLimitQueue()
        coord_a = _make_coord(hass_mock, [
            (ATOM_AUCKLAND, 200), (CAP_SEVERE, 200),  # poll 1
            (ATOM_EMPTY, 200),                         # poll 2 — alert expires
        ], "auckland", "https://example.com/a", rate_queue)
        coord_b = _make_coord(hass_mock, [
            (ATOM_WELLINGTON, 200), (CAP_EXTREME, 200),  # poll 1
            (ATOM_WELLINGTON, 200),                       # poll 2 — still active
        ], "wellington", "https://example.com/b", rate_queue)

        await coord_a._poll()
        await coord_b._poll()

        data_a_p2 = await coord_a._poll()
        data_b_p2 = await coord_b._poll()

        assert len(data_a_p2.alerts) == 0, "Feed A alert should have expired"
        assert len(data_b_p2.alerts) == 1, "Feed B alert should still be active"

    @pytest.mark.asyncio
    async def test_sensor_entities_scoped_to_correct_coordinator(self, hass_mock):
        """CAPAlertSensor from feed A should not read feed B's data."""
        rate_queue = RateLimitQueue()
        coord_a = _make_coord(hass_mock, [(ATOM_AUCKLAND, 200), (CAP_SEVERE, 200)], "auckland", "https://example.com/a", rate_queue)
        coord_b = _make_coord(hass_mock, [(ATOM_WELLINGTON, 200), (CAP_EXTREME, 200)], "wellington", "https://example.com/b", rate_queue)

        data_a = await coord_a._poll()
        data_b = await coord_b._poll()

        # Manually set coordinator.data (mimics what HA sets after first refresh)
        coord_a.data = data_a
        coord_b.data = data_b

        alert_id_a = next(iter(data_a.alerts))
        alert_id_b = next(iter(data_b.alerts))

        entity_a = CAPAlertSensor(coord_a, alert_id_a)
        entity_b = CAPAlertSensor(coord_b, alert_id_b)

        assert entity_a.state == "severe"
        assert entity_b.state == "extreme"
        assert entity_a.coordinator is coord_a
        assert entity_b.coordinator is coord_b


# ---------------------------------------------------------------------------
# Shared RateLimitQueue serialises across feeds
# ---------------------------------------------------------------------------

class TestSharedRateLimitQueue:
    @pytest.mark.asyncio
    async def test_shared_queue_counts_all_requests(self, hass_mock):
        rate_queue = RateLimitQueue(max_per_minute=20)
        coord_a = _make_coord(hass_mock, [(ATOM_AUCKLAND, 200), (CAP_SEVERE, 200)], "auckland", "https://example.com/a", rate_queue)
        coord_b = _make_coord(hass_mock, [(ATOM_WELLINGTON, 200), (CAP_EXTREME, 200)], "wellington", "https://example.com/b", rate_queue)

        await coord_a._poll()
        await coord_b._poll()

        # 2 Atom + 2 CAP docs = 4 requests in the shared queue
        assert len(rate_queue._request_times) == 4

    @pytest.mark.asyncio
    async def test_separate_queues_are_independent(self, hass_mock):
        queue_a = RateLimitQueue(max_per_minute=20)
        queue_b = RateLimitQueue(max_per_minute=20)
        coord_a = _make_coord(hass_mock, [(ATOM_AUCKLAND, 200), (CAP_SEVERE, 200)], "auckland", "https://example.com/a", queue_a)
        coord_b = _make_coord(hass_mock, [(ATOM_WELLINGTON, 200), (CAP_EXTREME, 200)], "wellington", "https://example.com/b", queue_b)

        await coord_a._poll()
        await coord_b._poll()

        assert len(queue_a._request_times) == 2
        assert len(queue_b._request_times) == 2


# ---------------------------------------------------------------------------
# Aggregate helpers span all feeds
# ---------------------------------------------------------------------------

class TestAggregateHelpersMultiFeed:
    def _make_sensor_coord(self, feed_name, alerts):
        coord = MagicMock()
        coord.feed_name = feed_name
        coord.data = FeedData(alerts=alerts)
        coord.async_add_listener = MagicMock(return_value=lambda: None)
        return coord

    def _alert(self, alert_id, severity="info", headline="Test Alert"):
        return ParsedAlert(
            alert_id=alert_id,
            entity_id_suffix=alert_id[:8],
            headline=headline,
            severity=severity,
            urgency="expected",
            certainty="likely",
            issued="2024-06-26T10:00:00Z",
            onset=None,
            expires=None,
            area="NZ",
            description="Test",
            instructions=None,
            geometry_polygon=None,
            cap_url=None,
            source=None,
            category=None,
        )

    def test_alert_count_sums_all_feeds(self):
        c1 = self._make_sensor_coord("a", {"x": self._alert("x"), "y": self._alert("y")})
        c2 = self._make_sensor_coord("b", {"z": self._alert("z")})
        sensor = CAPAlertCountSensor("entry1", [c1, c2])
        assert sensor.state == 3

    def test_highest_severity_picks_worst_across_feeds(self):
        c1 = self._make_sensor_coord("a", {"x": self._alert("x", "watch")})
        c2 = self._make_sensor_coord("b", {"y": self._alert("y", "extreme")})
        sensor = CAPHighestSeveritySensor("entry1", [c1, c2])
        assert sensor.state == "extreme"

    def test_highest_severity_none_when_all_feeds_empty(self):
        c1 = self._make_sensor_coord("a", {})
        c2 = self._make_sensor_coord("b", {})
        sensor = CAPHighestSeveritySensor("entry1", [c1, c2])
        assert sensor.state == "none"

    def test_latest_headline_picks_highest_severity_alert(self):
        c1 = self._make_sensor_coord("a", {"x": self._alert("x", "warning", "Warning in Auckland")})
        c2 = self._make_sensor_coord("b", {"y": self._alert("y", "severe", "Severe in Wellington")})
        sensor = CAPLatestHeadlineSensor("entry1", [c1, c2])
        assert sensor.state == "Severe in Wellington"

    def test_latest_headline_attribute_traces_back_to_feed(self):
        c1 = self._make_sensor_coord("auckland_feed", {"x": self._alert("x", "extreme", "Extreme!")})
        c2 = self._make_sensor_coord("wellington_feed", {"y": self._alert("y", "info", "FYI")})
        sensor = CAPLatestHeadlineSensor("entry1", [c1, c2])
        assert sensor.extra_state_attributes["feed_name"] == "auckland_feed"


# ---------------------------------------------------------------------------
# async_setup_entry with two coordinators
# ---------------------------------------------------------------------------

class TestSetupEntryMultiCoordinator:
    def _mock_coord(self, feed_name, alerts=None):
        coord = MagicMock()
        coord.feed_name = feed_name
        coord.last_update_success = True
        coord.data = FeedData(alerts=alerts or {})
        coord.async_add_listener = MagicMock(return_value=lambda: None)
        coord.hass = MagicMock()
        return coord

    @pytest.mark.asyncio
    async def test_registers_one_listener_per_coordinator(self):
        coord_a = self._mock_coord("auckland")
        coord_b = self._mock_coord("wellington")

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "eid": {"coordinators": {"auckland": coord_a, "wellington": coord_b}}
            }
        }
        hass.async_create_task = MagicMock(side_effect=lambda c: c.close() or MagicMock())

        entry = MagicMock()
        entry.entry_id = "eid"
        entry.async_on_unload = MagicMock()

        await async_setup_entry(hass, entry, MagicMock())

        coord_a.async_add_listener.assert_called_once()
        coord_b.async_add_listener.assert_called_once()

    @pytest.mark.asyncio
    async def test_adds_alert_entities_from_both_coordinators(self):
        alert_a = ParsedAlert("a1", "a1", "Alert A", "severe", "expected", "likely",
                              "2024-01-01T00:00:00Z", None, None, "AKL", "Desc", None, None, None, None, None)
        alert_b = ParsedAlert("b1", "b1", "Alert B", "extreme", "immediate", "observed",
                              "2024-01-01T00:00:00Z", None, None, "WLG", "Desc", None, None, None, None, None)

        coord_a = self._mock_coord("auckland", {"a1": alert_a})
        coord_b = self._mock_coord("wellington", {"b1": alert_b})

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "eid": {"coordinators": {"auckland": coord_a, "wellington": coord_b}}
            }
        }
        hass.async_create_task = MagicMock(side_effect=lambda c: c.close() or MagicMock())

        entry = MagicMock()
        entry.entry_id = "eid"
        entry.async_on_unload = MagicMock()

        added = []
        await async_setup_entry(hass, entry, lambda e: added.extend(e))

        alert_entities = [e for e in added if isinstance(e, CAPAlertSensor)]
        assert len(alert_entities) == 2
        feed_names = {e.coordinator.feed_name for e in alert_entities}
        assert feed_names == {"auckland", "wellington"}
