"""
Step 10 — Live Home Assistant QA checklist.

These tests are NOT automated. Each test documents a manual QA step for
validating the integration on a real Home Assistant instance.

Run the whole file to see all skipped tests and their reasons:
    pytest tests/test_step10_live_ha_qa.py -v

To mark a step done during a QA session, temporarily change:
    @pytest.mark.skip(reason="manual QA ...")
to:
    @pytest.mark.skip(reason="DONE — <date>")

Prerequisites:
  - HA 2024.1+ running locally or in a dev container
  - custom_components/ha_capwatcher/ copied into config/custom_components/
  - HA restarted after copy
  - Network access to https://alerts.sshadmin.dev from the HA host
"""

import pytest

MANUAL_QA = pytest.mark.skip(reason="manual QA — requires live HA instance")


# ---------------------------------------------------------------------------
# 1. Installation
# ---------------------------------------------------------------------------

class TestInstallation:
    @MANUAL_QA
    def test_integration_appears_in_add_integration_list(self):
        """
        In HA: Settings → Devices & Services → + Add Integration.
        Type "CAPWatcher" — the integration must appear in the list.
        If it does not appear, check that __init__.py, manifest.json, and
        config_flow.py are all present under custom_components/ha_capwatcher/.
        """

    @MANUAL_QA
    def test_no_startup_errors_in_ha_log(self):
        """
        After HA restart, open Settings → System → Logs.
        Filter by 'ha_capwatcher'. There should be no ERROR or CRITICAL lines.
        Informational lines about coordinators starting are expected.
        """

    @MANUAL_QA
    def test_manifest_version_shown_in_integrations_ui(self):
        """
        In HA: Settings → Devices & Services → HA-CAPWatcher → (gear icon) → Info.
        Confirm version shows 0.1.0 as defined in manifest.json.
        """


# ---------------------------------------------------------------------------
# 2. Config flow
# ---------------------------------------------------------------------------

class TestConfigFlow:
    @MANUAL_QA
    def test_config_flow_shows_feed_selector(self):
        """
        Add the integration. The first screen should show:
        - A multi-select (or checkbox list) of available feeds, with
          'official_all_nz' pre-ticked.
        - A polling interval dropdown defaulting to '1 minute'.
        """

    @MANUAL_QA
    def test_config_flow_creates_entry_with_official_all_nz(self):
        """
        Select only 'official_all_nz', leave interval at '1 minute', submit.
        The integration should be created with no errors.
        A new entry appears in Devices & Services.
        """

    @MANUAL_QA
    def test_options_flow_lets_you_change_interval(self):
        """
        Click the integration entry → Options (or Configure).
        Change polling interval to 30 seconds, save.
        Check HA logs — coordinator should restart at the new interval.
        Change back to 1 minute when done.
        """

    @MANUAL_QA
    def test_options_flow_lets_you_add_regional_feed(self):
        """
        Open Options, add a second feed (e.g. 'region_auckland').
        Confirm both feeds appear as separate coordinator entries in HA logs.
        """


# ---------------------------------------------------------------------------
# 3. Sensor entities
# ---------------------------------------------------------------------------

class TestSensorEntities:
    @MANUAL_QA
    def test_three_aggregate_sensors_appear(self):
        """
        After setup, go to Developer Tools → States.
        Filter by 'ha_capwatcher'. Confirm these three entities exist:
          sensor.ha_capwatcher_<entry>_alert_count
          sensor.ha_capwatcher_<entry>_highest_severity
          sensor.ha_capwatcher_<entry>_latest_headline

        Note: <entry> reflects the entry title (usually 'ha_capwatcher').
        """

    @MANUAL_QA
    def test_alert_count_is_a_number(self):
        """
        sensor.ha_capwatcher_<entry>_alert_count state should be an integer.
        May be 0 if no active alerts in NZ right now — that is valid.
        Confirm the 'by_feed' attribute is a dict (even if empty).
        """

    @MANUAL_QA
    def test_highest_severity_valid_value(self):
        """
        sensor.ha_capwatcher_<entry>_highest_severity state should be one of:
          extreme / severe / warning / watch / info / none
        If no alerts, state should be 'none'.
        """

    @MANUAL_QA
    def test_latest_headline_not_error(self):
        """
        sensor.ha_capwatcher_<entry>_latest_headline:
        - If alerts active: state = headline string (non-empty).
        - If no alerts: state = None (or 'unavailable' in HA).
        Extra attributes should include severity, area, issued, feed_name
        when an alert is present.
        """

    @MANUAL_QA
    def test_individual_alert_sensors_appear_when_alerts_active(self):
        """
        If NZ has any active CAP alerts, one sensor per alert should appear:
          sensor.ha_capwatcher_<feed_name>_<8char_id>
        State = severity string (e.g. 'warning').
        Attributes should include headline, area, description, cap_url.
        """

    @MANUAL_QA
    def test_alert_sensor_severity_color_attribute(self):
        """
        On any active alert sensor, check extra attributes:
          severity_color  — a hex string like '#FF8918'
          severity_background — a hex string or null for 'info'
        """


# ---------------------------------------------------------------------------
# 4. Alert lifecycle
# ---------------------------------------------------------------------------

class TestAlertLifecycle:
    @MANUAL_QA
    def test_new_alert_appears_within_one_poll_cycle(self):
        """
        When a new NZ CAP alert is issued, the sensor should appear within
        the configured polling interval (default 1 minute).
        Verify by watching Developer Tools → States and waiting for the feed
        to update. Log line 'Fetching CAP doc' should appear.
        """

    @MANUAL_QA
    def test_expired_alert_sensor_removed(self):
        """
        When an alert is no longer in the Atom feed (expired or cancelled),
        the corresponding sensor entity should be removed automatically.
        It should not linger as 'unavailable' — it should disappear.
        Check Developer Tools → States to confirm.
        """

    @MANUAL_QA
    def test_alert_count_decrements_on_expiry(self):
        """
        When an alert expires, sensor.ha_capwatcher_<entry>_alert_count should
        decrement by 1 on the next poll. Verify via state history.
        """

    @MANUAL_QA
    def test_highest_severity_updates_when_extreme_alert_expires(self):
        """
        If the only 'extreme' alert expires, highest_severity should drop to
        the next worst level. Verify by checking state history.
        """


# ---------------------------------------------------------------------------
# 5. Error handling and resilience
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @MANUAL_QA
    def test_feed_goes_offline_gracefully(self):
        """
        Temporarily block network access to alerts.sshadmin.dev (e.g. via /etc/hosts).
        After MAX_RETRY_ATTEMPTS (5) failed polls, existing alert sensors should
        become 'unavailable' (coordinator offline).
        Restore network access — coordinator should auto-recover on next poll.
        """

    @MANUAL_QA
    def test_rate_limit_429_backoff(self):
        """
        With multiple feeds polling fast, watch HA logs for any 429 responses.
        On 429, coordinator should log a warning and back off to 5-minute interval.
        Other feeds should continue polling normally.
        """

    @MANUAL_QA
    def test_ha_restart_retains_integration_config(self):
        """
        Restart HA (Settings → System → Restart).
        After restart, the integration should load automatically with the same
        feeds and interval configured before restart.
        Sensors should restore to their previous state within one poll cycle.
        """

    @MANUAL_QA
    def test_reload_integration_without_restart(self):
        """
        Go to Settings → Devices & Services → HA-CAPWatcher → (three dots) → Reload.
        Integration should reload cleanly. Verify in HA logs that:
        - 'async_unload_entry' succeeded
        - 'async_setup_entry' completed with no errors
        - Sensors are available again within one poll cycle
        """


# ---------------------------------------------------------------------------
# 6. Multi-feed
# ---------------------------------------------------------------------------

class TestMultiFeed:
    @MANUAL_QA
    def test_two_feeds_both_poll_independently(self):
        """
        Configure two feeds (e.g. official_all_nz + region_auckland).
        Watch HA logs — both coordinators should log poll activity independently.
        Alerts from each feed should be prefixed with their feed name in entity IDs.
        """

    @MANUAL_QA
    def test_aggregate_helpers_span_all_feeds(self):
        """
        With two feeds active, sensor.ha_capwatcher_<entry>_alert_count should
        sum alerts from both feeds. Confirm 'by_feed' attribute shows per-feed
        counts that add up to the total.
        """

    @MANUAL_QA
    def test_unloading_one_entry_does_not_affect_other_entries(self):
        """
        If you have two integration config entries, removing one via
        Settings → Devices & Services should only remove that entry's sensors.
        The other entry's sensors should remain active and polling.
        """


# ---------------------------------------------------------------------------
# 7. Lovelace / dashboard display
# ---------------------------------------------------------------------------

class TestDashboard:
    @MANUAL_QA
    def test_alert_count_sensor_usable_in_lovelace_card(self):
        """
        Add an Entities card to a dashboard, add:
          sensor.ha_capwatcher_<entry>_alert_count
        Confirm it shows a number, not an error.
        """

    @MANUAL_QA
    def test_automation_triggers_on_severity_change(self):
        """
        Create a simple automation:
          trigger: state of sensor.ha_capwatcher_<entry>_highest_severity
          condition: state != 'none'
          action: persistent_notification.create with message="{{ states(...) }}"
        Trigger manually via Developer Tools → Services, or wait for a real alert.
        Confirm the automation fires and the notification appears.
        """

    @MANUAL_QA
    def test_template_sensor_reads_alert_attribute(self):
        """
        In Developer Tools → Template, test:
          {{ state_attr('sensor.ha_capwatcher_<entry>_latest_headline', 'severity') }}
        Should return a severity string (or None if no alerts).
        This confirms attributes are accessible to template sensors and automations.
        """


# ---------------------------------------------------------------------------
# 8. HACS compatibility (optional — skip if not using HACS)
# ---------------------------------------------------------------------------

class TestHACSCompatibility:
    @MANUAL_QA
    def test_hacs_recognises_integration(self):
        """
        In HACS, go to Integrations → Custom repositories.
        Add this repo URL. Confirm HACS shows the integration name,
        version, and a description without errors.
        """

    @MANUAL_QA
    def test_hacs_install_flow_works_end_to_end(self):
        """
        Via HACS, install HA-CAPWatcher. Restart HA.
        Confirm the integration appears in Add Integration and the full
        setup flow completes without errors (duplicate of TestInstallation,
        but via HACS distribution path).
        """
