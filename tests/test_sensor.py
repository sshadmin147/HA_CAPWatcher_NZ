"""Tests for CAPAlertSensor entity lifecycle and properties."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from custom_components.ha_capwatcher.coordinator import FeedData
from custom_components.ha_capwatcher.parser import ParsedAlert
from custom_components.ha_capwatcher.sensor import CAPAlertSensor, async_setup_entry
from custom_components.ha_capwatcher.const import DOMAIN


# --- Fixtures ---

def _make_alert(
    alert_id: str = "abc123",
    headline: str = "Severe Wind Warning",
    severity: str = "severe",
    urgency: str = "expected",
    certainty: str = "likely",
    area: str = "Auckland",
    description: str = "Strong winds.",
) -> ParsedAlert:
    return ParsedAlert(
        alert_id=alert_id,
        entity_id_suffix=alert_id[:8],
        headline=headline,
        severity=severity,
        urgency=urgency,
        certainty=certainty,
        issued="2024-06-26T10:00:00Z",
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


@pytest.fixture
def mock_coordinator():
    coord = MagicMock()
    coord.feed_name = "official_all_nz"
    coord.last_update_success = True
    coord.data = FeedData(alerts={})
    coord.async_add_listener = MagicMock(return_value=lambda: None)
    coord.hass = MagicMock()
    return coord


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def hass_mock(mock_coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": {"coordinator": mock_coordinator}}}

    def _schedule(coro):
        if hasattr(coro, "close"):
            coro.close()
        return MagicMock()

    hass.async_create_task = MagicMock(side_effect=_schedule)
    return hass


# --- Entity property tests ---

class TestCAPAlertSensorProperties:
    def _entity(self, coordinator, alert_id="abc123"):
        return CAPAlertSensor(coordinator, alert_id)

    def test_unique_id_includes_domain_feed_and_alert(self, mock_coordinator):
        entity = self._entity(mock_coordinator)
        assert entity.unique_id == f"{DOMAIN}_official_all_nz_abc123"

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
        mock_coordinator.data = FeedData(alerts={})  # no alerts
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
        assert attrs["description"] == "Strong winds."
        assert attrs["cap_url"] == "https://nzalerts.co.nz/cap/alerts/1"
        assert attrs["source"] == "MetService"
        assert attrs["feed_name"] == "official_all_nz"

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

    def test_extra_attributes_info_severity_has_no_background(self, mock_coordinator):
        alert = _make_alert(alert_id="abc123", severity="info")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})
        entity = self._entity(mock_coordinator)
        assert entity.extra_state_attributes["severity_background"] is None

    def test_icon_is_alert(self, mock_coordinator):
        entity = self._entity(mock_coordinator)
        assert entity._attr_icon == "mdi:alert"


# --- Lifecycle tests (async_setup_entry) ---

class TestEntityLifecycle:
    @pytest.mark.asyncio
    async def test_registers_listener_on_coordinator(
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
    async def test_no_entities_added_when_feed_empty(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        added = []
        mock_coordinator.data = FeedData(alerts={})
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        assert added == []

    @pytest.mark.asyncio
    async def test_no_entities_added_when_data_none(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        added = []
        mock_coordinator.data = None
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        assert added == []

    @pytest.mark.asyncio
    async def test_adds_entity_for_new_alert(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))

        assert len(added) == 1
        assert isinstance(added[0], CAPAlertSensor)
        assert added[0]._alert_id == "abc123"

    @pytest.mark.asyncio
    async def test_adds_multiple_entities_for_multiple_alerts(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        mock_coordinator.data = FeedData(alerts={
            "a1": _make_alert("a1"),
            "a2": _make_alert("a2"),
        })

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        assert len(added) == 2

    @pytest.mark.asyncio
    async def test_no_duplicate_entities_on_second_update(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))

        # Fire the registered callback a second time (same alert still in feed)
        update_callback = mock_coordinator.async_add_listener.call_args[0][0]
        update_callback()

        assert len(added) == 1  # entity added once only

    @pytest.mark.asyncio
    async def test_removes_entity_when_alert_expires(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        alert = _make_alert(alert_id="abc123")
        mock_coordinator.data = FeedData(alerts={"abc123": alert})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        assert len(added) == 1

        # Alert disappears from feed
        mock_coordinator.data = FeedData(alerts={})
        update_callback = mock_coordinator.async_add_listener.call_args[0][0]
        update_callback()

        # async_remove should have been scheduled
        hass_mock.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_alert_added_on_second_update(
        self, hass_mock, mock_entry, mock_coordinator
    ):
        mock_coordinator.data = FeedData(alerts={"a1": _make_alert("a1")})

        added = []
        await async_setup_entry(hass_mock, mock_entry, lambda e: added.extend(e))
        assert len(added) == 1

        # Second alert arrives in next poll
        mock_coordinator.data = FeedData(alerts={
            "a1": _make_alert("a1"),
            "a2": _make_alert("a2"),
        })
        update_callback = mock_coordinator.async_add_listener.call_args[0][0]
        update_callback()

        assert len(added) == 2
