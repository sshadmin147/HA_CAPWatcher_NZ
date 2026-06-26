"""Tests for CAPAlertSensor, lifecycle, and aggregate helper entities."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.ha_capwatcher.coordinator import FeedData
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
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(
    alert_id: str = "abc123",
    headline: str = "Severe Wind Warning",
    severity: str = "severe",
    urgency: str = "expected",
    certainty: str = "likely",
    area: str = "Auckland",
    description: str = "Strong winds.",
    issued: str = "2024-06-26T10:00:00Z",
) -> ParsedAlert:
    return ParsedAlert(
        alert_id=alert_id,
        entity_id_suffix=alert_id[:8],
        headline=headline,
        severity=severity,
        urgency=urgency,
        certainty=certainty,
        issued=issued,
        onset=None,
        expires="2024-06-26T18:00:00Z",
        area=area,
        description=description,
        instructions=None,
        geometry_polygon=None,
        cap_url="https://nzalerts.co.nz/cap/alerts/1",
        source="MetService",
        category="Met",
    )


def _make_coordinator(feed_name="feed_a", alerts=None):
    coord = MagicMock()
    coord.feed_name = feed_name
    coord.last_update_success = True
    coord.data = FeedData(alerts=alerts or {})
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    coord.hass = MagicMock()
    return coord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_coordinator():
    return _make_coordinator()


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def hass_mock(mock_coordinator):
    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            "test_entry": {
                "coordinators": {"feed_a": mock_coordinator},
            }
        }
    }

    def _schedule(coro):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()

    hass.async_create_task = MagicMock(side_effect=_schedule)
    return hass


# ---------------------------------------------------------------------------
# CAPAlertSensor property tests
# ---------------------------------------------------------------------------

class TestCAPAlertSensorProperties:
    def _entity(self, coordinator, alert_id="abc123"):
        return CAPAlertSensor(coordinator, alert_id)

    def test_unique_id_includes_domain_feed_and_alert(self, mock_coordinator):
        entity = self._entity(mock_coordinator)
        assert entity.unique_id == f"{DOMAIN}_feed_a_abc123"

    def test_name_returns_alert_headline(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123", headline="Severe Wind Warning")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        assert entity.name == "Severe Wind Warning"

    def test_name_fallback_when_no_data(self, mock_coordinator):
        mock_coordinator.data = None
        entity = self._entity(mock_coordinator)
        assert "abc123" in entity.name

    def test_state_returns_severity(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123", severity="severe")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        assert entity.state == "severe"

    def test_state_none_when_no_data(self, mock_coordinator):
        mock_coordinator.data = None
        entity = self._entity(mock_coordinator)
        assert entity.state is None

    def test_state_none_when_alert_not_in_data(self, mock_coordinator):
        mock_coordinator.data = FeedData(alerts={})
        entity = self._entity(mock_coordinator)
        assert entity.state is None

    def test_available_true_when_alert_present(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        assert entity.available is True

    def test_available_false_when_alert_missing_from_feed(self, mock_coordinator):
        mock_coordinator.data = FeedData(alerts={})
        entity = self._entity(mock_coordinator)
        assert entity.available is False

    def test_available_false_when_data_is_none(self, mock_coordinator):
        mock_coordinator.data = None
        entity = self._entity(mock_coordinator)
        assert entity.available is False

    def test_available_false_when_coordinator_failed(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        mock_coordinator.last_update_success = False
        entity = self._entity(mock_coordinator)
        assert entity.available is False

    def test_extra_attributes_all_fields_present(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        attrs = entity.extra_state_attributes

        assert attrs["headline"] == "Severe Wind Warning"
        assert attrs["urgency"] == "expected"
        assert attrs["certainty"] == "likely"
        assert attrs["area"] == "Auckland"
        assert attrs["cap_url"] == "https://nzalerts.co.nz/cap/alerts/1"
        assert attrs["source"] == "MetService"
        assert attrs["feed_name"] == "feed_a"

    def test_extra_attributes_includes_severity_color(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123", severity="severe")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        attrs = entity.extra_state_attributes
        assert attrs["severity_color"] == "#FF181E"
        assert attrs["severity_background"] == "#fde8e8"

    def test_extra_attributes_empty_when_alert_gone(self, mock_coordinator):
        mock_coordinator.data = FeedData(alerts={})
        entity = self._entity(mock_coordinator)
        assert entity.extra_state_attributes == {}

    def test_extra_attributes_info_severity_background_is_none(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123", severity="info")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        assert entity.extra_state_attributes["severity_background"] is None

    def test_icon_is_mdi_alert(self, mock_coordinator):
        entity = self._entity(mock_coordinator)
        assert entity._attr_icon == "mdi:alert"


# ---------------------------------------------------------------------------
# async_setup_entry lifecycle tests
# ---------------------------------------------------------------------------

class TestEntityLifecycle:
    @pytest.mark.asyncio
    async def test_registers_listener_on_each_coordinator(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        await async_setup_entry(hass_mock, mock_entry, MagicMock())
        mock_coordinator.async_add_listener.assert_called_once()

    @pytest.mark.asyncio
    async def test_wraps_listener_in_on_unload(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        await async_setup_entry(hass_mock, mock_entry, MagicMock())
        mock_entry.async_on_unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_helper_entities_always_added(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        mock_coordinator.data = FeedData(alerts={})
        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        helper_types = (CAPAlertCountSensor, CAPHighestSeveritySensor, CAPLatestHeadlineSensor)
        helpers = [e for e in added if isinstance(e, helper_types)]
        assert len(helpers) == 3

    @pytest.mark.asyncio
    async def test_adds_alert_entity_for_new_alert(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))

        alert_entities = [e for e in added if isinstance(e, CAPAlertSensor)]
        assert len(alert_entities) == 1
        assert alert_entities[0]._alert_id == "abc123"

    @pytest.mark.asyncio
    async def test_no_duplicate_entities_on_second_update(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        initial_count = len([e for e in added if isinstance(e, CAPAlertSensor)])

        update_cb = mock_coordinator.async_add_listener.call_args[0][0]
        update_cb()

        alert_count = len([e for e in added if isinstance(e, CAPAlertSensor)])
        assert alert_count == initial_count

    @pytest.mark.asyncio
    async def test_removes_entity_when_alert_expires(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        await async_setup_entry(hass_mock, mock_entry, MagicMock())

        mock_coordinator.data = FeedData(alerts={})
        update_cb = mock_coordinator.async_add_listener.call_args[0][0]
        update_cb()

        hass_mock.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_alert_entity_added_on_second_update(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        mock_coordinator.data = FeedData(alerts={"a1": _make_alert("a1")})
        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))

        mock_coordinator.data = FeedData(alerts={
            "a1": _make_alert("a1"),
            "a2": _make_alert("a2"),
        })
        update_cb = mock_coordinator.async_add_listener.call_args[0][0]
        update_cb()

        alert_entities = [e for e in added if isinstance(e, CAPAlertSensor)]
        assert len(alert_entities) == 2


# ---------------------------------------------------------------------------
# Aggregate helper entity tests
# ---------------------------------------------------------------------------

class TestCAPAlertCountSensor:
    def test_state_zero_with_no_alerts(self):
        coord = _make_coordinator(alerts={})
        sensor = CAPAlertCountSensor("entry1", [coord])
        assert sensor.state == 0

    def test_state_counts_all_alerts(self):
        coord = _make_coordinator(alerts={"a": _make_alert("a"), "b": _make_alert("b")})
        sensor = CAPAlertCountSensor("entry1", [coord])
        assert sensor.state == 2

    def test_state_sums_across_coordinators(self):
        c1 = _make_coordinator("feed_a", {"a": _make_alert("a")})
        c2 = _make_coordinator("feed_b", {"b": _make_alert("b"), "c": _make_alert("c")})
        sensor = CAPAlertCountSensor("entry1", [c1, c2])
        assert sensor.state == 3

    def test_unique_id_format(self):
        sensor = CAPAlertCountSensor("myentry", [])
        assert sensor.unique_id == f"{DOMAIN}_myentry_alert_count"

    def test_attributes_include_per_feed_breakdown(self):
        c1 = _make_coordinator("feed_a", {"a": _make_alert("a")})
        c2 = _make_coordinator("feed_b", {"b": _make_alert("b")})
        sensor = CAPAlertCountSensor("e1", [c1, c2])
        attrs = sensor.extra_state_attributes
        assert attrs["by_feed"]["feed_a"] == 1
        assert attrs["by_feed"]["feed_b"] == 1

    @pytest.mark.asyncio
    async def test_registers_listener_on_each_coordinator(self):
        c1 = _make_coordinator("feed_a")
        c2 = _make_coordinator("feed_b")
        sensor = CAPAlertCountSensor("e1", [c1, c2])
        await sensor.async_added_to_hass()
        c1.async_add_listener.assert_called_once()
        c2.async_add_listener.assert_called_once()


class TestCAPHighestSeveritySensor:
    def test_state_none_when_no_alerts(self):
        coord = _make_coordinator(alerts={})
        sensor = CAPHighestSeveritySensor("e1", [coord])
        assert sensor.state == "none"

    def test_state_returns_highest_severity(self):
        coord = _make_coordinator(alerts={
            "a": _make_alert("a", severity="warning"),
            "b": _make_alert("b", severity="extreme"),
        })
        sensor = CAPHighestSeveritySensor("e1", [coord])
        assert sensor.state == "extreme"

    def test_state_aggregates_across_feeds(self):
        c1 = _make_coordinator("feed_a", {"a": _make_alert("a", severity="watch")})
        c2 = _make_coordinator("feed_b", {"b": _make_alert("b", severity="severe")})
        sensor = CAPHighestSeveritySensor("e1", [c1, c2])
        assert sensor.state == "severe"

    def test_attributes_include_severity_color(self):
        coord = _make_coordinator(alerts={"a": _make_alert("a", severity="severe")})
        sensor = CAPHighestSeveritySensor("e1", [coord])
        attrs = sensor.extra_state_attributes
        assert attrs["severity_color"] == "#FF181E"
        assert attrs["severity_background"] == "#fde8e8"

    def test_unique_id_format(self):
        sensor = CAPHighestSeveritySensor("myentry", [])
        assert sensor.unique_id == f"{DOMAIN}_myentry_highest_severity"


class TestCAPLatestHeadlineSensor:
    def test_state_none_when_no_alerts(self):
        coord = _make_coordinator(alerts={})
        sensor = CAPLatestHeadlineSensor("e1", [coord])
        assert sensor.state is None

    def test_state_returns_highest_priority_headline(self):
        coord = _make_coordinator(alerts={
            "a": _make_alert("a", severity="watch", headline="Watch Alert"),
            "b": _make_alert("b", severity="severe", headline="Severe Alert"),
        })
        sensor = CAPLatestHeadlineSensor("e1", [coord])
        assert sensor.state == "Severe Alert"

    def test_state_picks_highest_severity_across_feeds(self):
        c1 = _make_coordinator("feed_a", {"a": _make_alert("a", severity="info", headline="Info")})
        c2 = _make_coordinator("feed_b", {"b": _make_alert("b", severity="extreme", headline="Extreme!")})
        sensor = CAPLatestHeadlineSensor("e1", [c1, c2])
        assert sensor.state == "Extreme!"

    def test_attributes_include_feed_name(self):
        coord = _make_coordinator("official", {"a": _make_alert("a", severity="severe")})
        sensor = CAPLatestHeadlineSensor("e1", [coord])
        attrs = sensor.extra_state_attributes
        assert attrs["feed_name"] == "official"

    def test_attributes_empty_when_no_alerts(self):
        sensor = CAPLatestHeadlineSensor("e1", [_make_coordinator(alerts={})])
        assert sensor.extra_state_attributes == {}

    def test_unique_id_format(self):
        sensor = CAPLatestHeadlineSensor("myentry", [])
        assert sensor.unique_id == f"{DOMAIN}_myentry_latest_headline"
