"""Tests for CAP/Atom feed parser."""

import pytest
from custom_components.ha_capwatcher.parser import (
    AtomEntry,
    ParsedAlert,
    parse_atom_feed,
    parse_cap_document,
)

# --- Fixtures: minimal valid Atom + CAP XML ---

VALID_ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>NZ Alerts — Auckland</title>
  <entry>
    <title>Severe Wind Warning</title>
    <id>tag:alerts.sshadmin.dev,2024:00123456</id>
    <updated>2024-06-26T10:00:00Z</updated>
    <published>2024-06-26T10:00:00Z</published>
    <author><name>MetService</name></author>
    <category term="Met"/>
    <summary>Strong northerly winds expected across Auckland region.</summary>
    <link rel="related" type="application/cap+xml"
          href="https://alerts.sshadmin.dev/cap/alerts/123456"/>
  </entry>
</feed>"""

VALID_CAP_DOCUMENT = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>nzalerts-123456</identifier>
  <sender>metservice.com</sender>
  <sent>2024-06-26T10:00:00Z</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <info>
    <category>Met</category>
    <event>Wind Warning</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <onset>2024-06-26T12:00:00Z</onset>
    <expires>2024-06-27T00:00:00Z</expires>
    <description>Strong northerly winds 90-110 km/h expected.</description>
    <instruction>Secure outdoor furniture. Avoid travel if possible.</instruction>
    <area>
      <areaDesc>Auckland Region</areaDesc>
      <polygon>-36.5,174.5 -36.5,175.0 -37.0,175.0 -37.0,174.5 -36.5,174.5</polygon>
    </area>
  </info>
</alert>"""

ATOM_FEED_MISSING_ID = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Bad Entry</title>
    <updated>2024-06-26T10:00:00Z</updated>
  </entry>
</feed>"""

ATOM_FEED_MISSING_ISSUED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>tag:alerts.sshadmin.dev,2024:99999</id>
    <title>Bad Entry</title>
  </entry>
</feed>"""

CAP_DOCUMENT_MISSING_SEVERITY = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <certainty>Likely</certainty>
  </info>
</alert>"""

CAP_DOCUMENT_UNKNOWN_SEVERITY = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <severity>SuperDangerous</severity>
    <certainty>Likely</certainty>
  </info>
</alert>"""

CAP_DOCUMENT_WITH_CIRCLE = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Immediate</urgency>
    <severity>Extreme</severity>
    <certainty>Observed</certainty>
    <description>Civil defence emergency.</description>
    <area>
      <areaDesc>Wellington City</areaDesc>
      <circle>-41.2865,174.7762 10.0</circle>
    </area>
  </info>
</alert>"""

CAP_DOCUMENT_NO_NAMESPACE = """<?xml version="1.0" encoding="UTF-8"?>
<alert>
  <info>
    <urgency>Expected</urgency>
    <severity>Warning</severity>
    <certainty>Likely</certainty>
    <description>No-namespace CAP document.</description>
    <area>
      <areaDesc>Test Region</areaDesc>
    </area>
  </info>
</alert>"""

MALFORMED_XML = "this is not xml <<<"

_DUMMY_ENTRY = AtomEntry(
    alert_id="00123456",
    raw_id="tag:alerts.sshadmin.dev,2024:00123456",
    headline="Severe Wind Warning",
    issued="2024-06-26T10:00:00Z",
    cap_url="https://alerts.sshadmin.dev/cap/alerts/123456",
    source="MetService",
    category="Met",
    summary="Strong northerly winds expected.",
)

# --- Atom feed parsing tests ---

class TestParseAtomFeed:
    def test_parses_valid_entry(self):
        entries = parse_atom_feed(VALID_ATOM_FEED, "test")
        assert len(entries) == 1
        e = entries[0]
        assert e.headline == "Severe Wind Warning"
        assert e.issued == "2024-06-26T10:00:00Z"
        assert e.source == "MetService"
        assert e.category == "Met"
        assert e.summary == "Strong northerly winds expected across Auckland region."
        assert e.cap_url == "https://alerts.sshadmin.dev/cap/alerts/123456"

    def test_stable_id_from_tag_uri(self):
        entries = parse_atom_feed(VALID_ATOM_FEED, "test")
        assert entries[0].alert_id == "00123456"

    def test_skips_entry_missing_id(self):
        entries = parse_atom_feed(ATOM_FEED_MISSING_ID, "test")
        assert entries == []

    def test_skips_entry_missing_issued(self):
        entries = parse_atom_feed(ATOM_FEED_MISSING_ISSUED, "test")
        assert entries == []

    def test_returns_empty_on_malformed_xml(self):
        entries = parse_atom_feed(MALFORMED_XML, "test")
        assert entries == []

    def test_returns_empty_on_empty_feed(self):
        entries = parse_atom_feed(
            '<feed xmlns="http://www.w3.org/2005/Atom"></feed>', "test"
        )
        assert entries == []


# --- CAP document parsing tests ---

class TestParseCAPDocument:
    def test_parses_full_valid_document(self):
        alert = parse_cap_document(VALID_CAP_DOCUMENT, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "severe"
        assert alert.urgency == "expected"
        assert alert.certainty == "likely"
        assert alert.onset == "2024-06-26T12:00:00Z"
        assert alert.expires == "2024-06-27T00:00:00Z"
        assert alert.area == "Auckland Region"
        assert "northerly winds" in alert.description
        assert "Secure outdoor" in alert.instructions
        assert alert.geometry_polygon is not None
        assert "-36.5,174.5" in alert.geometry_polygon

    def test_entity_id_suffix_correct_length(self):
        alert = parse_cap_document(VALID_CAP_DOCUMENT, _DUMMY_ENTRY, "test")
        assert len(alert.entity_id_suffix) == 8

    def test_skips_alert_missing_severity(self):
        alert = parse_cap_document(CAP_DOCUMENT_MISSING_SEVERITY, _DUMMY_ENTRY, "test")
        assert alert is None

    def test_skips_alert_unknown_severity(self):
        alert = parse_cap_document(CAP_DOCUMENT_UNKNOWN_SEVERITY, _DUMMY_ENTRY, "test")
        assert alert is None

    def test_severity_normalized_to_lowercase(self):
        alert = parse_cap_document(VALID_CAP_DOCUMENT, _DUMMY_ENTRY, "test")
        assert alert.severity == "severe"
        assert alert.urgency == "expected"
        assert alert.certainty == "likely"

    def test_parses_circle_geometry(self):
        alert = parse_cap_document(CAP_DOCUMENT_WITH_CIRCLE, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "extreme"
        assert alert.geometry_polygon == "-41.2865,174.7762 10.0"

    def test_falls_back_to_atom_summary_when_no_description(self):
        entry_no_summary = AtomEntry(
            alert_id="99",
            raw_id="tag:test:99",
            headline="Test",
            issued="2024-06-26T10:00:00Z",
            cap_url=None,
            source=None,
            category=None,
            summary="Fallback summary from Atom.",
        )
        cap_no_description = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <severity>Watch</severity>
    <certainty>Possible</certainty>
  </info>
</alert>"""
        alert = parse_cap_document(cap_no_description, entry_no_summary, "test")
        assert alert.description == "Fallback summary from Atom."

    def test_handles_no_namespace_cap_document(self):
        alert = parse_cap_document(CAP_DOCUMENT_NO_NAMESPACE, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.area == "Test Region"

    def test_returns_none_on_malformed_xml(self):
        alert = parse_cap_document(MALFORMED_XML, _DUMMY_ENTRY, "test")
        assert alert is None

    def test_returns_none_on_missing_info_block(self):
        cap_no_info = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
</alert>"""
        alert = parse_cap_document(cap_no_info, _DUMMY_ENTRY, "test")
        assert alert is None

    def test_preserves_atom_metadata(self):
        alert = parse_cap_document(VALID_CAP_DOCUMENT, _DUMMY_ENTRY, "test")
        assert alert.headline == "Severe Wind Warning"
        assert alert.issued == "2024-06-26T10:00:00Z"
        assert alert.source == "MetService"
        assert alert.category == "Met"
        assert alert.cap_url == "https://alerts.sshadmin.dev/cap/alerts/123456"

    def test_cap12_moderate_maps_to_warning(self):
        """CAP 1.2 Moderate (MetService Orange) must map to NZ-CAP 'warning'."""
        cap = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <description>Heavy Rain Warning - Orange.</description>
    <area><areaDesc>Canterbury</areaDesc></area>
  </info>
</alert>"""
        alert = parse_cap_document(cap, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "warning"

    def test_cap12_minor_maps_to_watch(self):
        """CAP 1.2 Minor (MetService Yellow) must map to NZ-CAP 'watch'."""
        cap = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Future</urgency>
    <severity>Minor</severity>
    <certainty>Possible</certainty>
    <description>Strong Wind Watch - Yellow.</description>
    <area><areaDesc>Wellington</areaDesc></area>
  </info>
</alert>"""
        alert = parse_cap_document(cap, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "watch"

    def test_cap12_unknown_maps_to_info(self):
        """CAP 1.2 Unknown severity must map to NZ-CAP 'info'."""
        cap = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Unknown</urgency>
    <severity>Unknown</severity>
    <certainty>Unknown</certainty>
    <description>Informational alert.</description>
    <area><areaDesc>New Zealand</areaDesc></area>
  </info>
</alert>"""
        alert = parse_cap_document(cap, _DUMMY_ENTRY, "test")
        assert alert is not None
        assert alert.severity == "info"

    def test_truly_unrecognized_severity_still_skipped(self):
        """A value that's neither NZ-CAP nor CAP 1.2 must still be rejected."""
        cap = """<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <info>
    <urgency>Expected</urgency>
    <severity>SuperDangerous</severity>
    <certainty>Likely</certainty>
    <area><areaDesc>NZ</areaDesc></area>
  </info>
</alert>"""
        alert = parse_cap_document(cap, _DUMMY_ENTRY, "test")
        assert alert is None
