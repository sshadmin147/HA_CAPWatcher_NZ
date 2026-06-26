"""CAP/Atom feed parser for HA-CAPWatcher."""

import logging
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

from .const import UUID_TRUNCATE_LENGTH
from .severity import validate_severity

_LOGGER = logging.getLogger(__name__)

# XML namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "cap": "urn:oasis:names:tc:emergency:cap:1.2",
}


@dataclass
class AtomEntry:
    """Lightweight alert parsed from the Atom feed listing."""

    alert_id: str           # Stable short ID for entity naming
    raw_id: str             # Full tag URI from feed
    headline: str
    issued: str
    cap_url: Optional[str]  # Link to full CAP document
    source: Optional[str]
    category: Optional[str]
    summary: Optional[str]  # Truncated description from Atom entry


@dataclass
class ParsedAlert:
    """
    Fully parsed CAP alert, ready for entity creation.
    Combines Atom entry fields with full CAP document fields.
    """

    alert_id: str
    entity_id_suffix: str
    headline: str
    severity: str
    urgency: str
    certainty: str
    issued: str
    onset: Optional[str]
    expires: Optional[str]
    area: Optional[str]
    description: Optional[str]
    instructions: Optional[str]
    geometry_polygon: Optional[str]
    cap_url: Optional[str]
    source: Optional[str]
    category: Optional[str]


def parse_atom_feed(xml_content: str, feed_name: str) -> list[AtomEntry]:
    """
    Parse an Atom feed and return lightweight entries.

    This is Phase 1 of a two-phase parse:
    - Phase 1 (here): Extract alert list + CAP document URLs from Atom feed
    - Phase 2 (parse_cap_document): Fetch each CAP doc for severity + full fields

    Args:
        xml_content: Raw XML string from feed response
        feed_name: Feed identifier for logging

    Returns:
        List of AtomEntry objects. Returns empty list on parse failure.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        _LOGGER.error("[%s] Malformed Atom XML: %s", feed_name, e)
        return []

    entries = root.findall("atom:entry", NS)
    _LOGGER.debug("[%s] Found %d entries in Atom feed", feed_name, len(entries))

    results = []
    for entry in entries:
        try:
            parsed = _parse_atom_entry(entry, feed_name)
            if parsed:
                results.append(parsed)
        except Exception as e:
            _LOGGER.error("[%s] Unexpected error parsing Atom entry: %s", feed_name, e)

    return results


def parse_cap_document(xml_content: str, atom_entry: AtomEntry, feed_name: str) -> Optional[ParsedAlert]:
    """
    Parse a full CAP 1.2 document and merge with Atom entry data.

    This is Phase 2 of a two-phase parse. Called once per alert on first
    encounter; subsequent polls use cached ParsedAlert data.

    Args:
        xml_content: Raw CAP XML from the individual alert document
        atom_entry: AtomEntry from Phase 1 (provides id, headline, source, etc.)
        feed_name: Feed identifier for logging

    Returns:
        ParsedAlert, or None if severity is missing or XML is malformed.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        _LOGGER.error("[%s] Malformed CAP XML for alert '%s': %s", feed_name, atom_entry.headline, e)
        return None

    # CAP document root is <alert>, info block is <alert><info>
    info = root.find("cap:info", NS)
    if info is None:
        # Some CAP documents use no namespace prefix
        info = root.find("info")
        if info is None:
            _LOGGER.error("[%s] CAP document missing <info> block for alert '%s'", feed_name, atom_entry.headline)
            return None

    # Severity is mandatory — skip alert loudly if missing
    raw_severity = _cap(info, "severity")
    try:
        severity = validate_severity(raw_severity)
    except ValueError as e:
        _LOGGER.error("[%s] Alert '%s' skipped: %s", feed_name, atom_entry.headline, e)
        return None

    urgency = (_cap(info, "urgency") or "unknown").lower()
    certainty = (_cap(info, "certainty") or "unknown").lower()
    onset = _cap(info, "onset")
    expires = _cap(info, "expires")
    area_el = info.find("cap:area", NS)
    if area_el is None:
        area_el = info.find("area")
    area = _cap(area_el, "areaDesc") if area_el is not None else None
    description = _cap(info, "description") or atom_entry.summary
    instructions = _cap(info, "instruction")
    geometry_polygon = _parse_geometry(info)

    return ParsedAlert(
        alert_id=atom_entry.alert_id,
        entity_id_suffix=atom_entry.alert_id[:UUID_TRUNCATE_LENGTH],
        headline=atom_entry.headline,
        severity=severity,
        urgency=urgency,
        certainty=certainty,
        issued=atom_entry.issued,
        onset=onset,
        expires=expires,
        area=area,
        description=description,
        instructions=instructions,
        geometry_polygon=geometry_polygon,
        cap_url=atom_entry.cap_url,
        source=atom_entry.source,
        category=atom_entry.category,
    )


# --- Private helpers ---

def _parse_atom_entry(entry: ET.Element, feed_name: str) -> Optional[AtomEntry]:
    """Parse a single <entry> from an Atom feed."""

    raw_id = _atom(entry, "id")
    if not raw_id:
        _LOGGER.warning("[%s] Entry missing <id>, skipping", feed_name)
        return None

    headline = _atom(entry, "title") or "Unknown Alert"
    issued = _atom(entry, "updated") or _atom(entry, "published")
    if not issued:
        _LOGGER.warning("[%s] Entry '%s' missing issued time, skipping", feed_name, headline)
        return None

    cap_url = None
    for link in entry.findall("atom:link", NS):
        if link.get("type") == "application/cap+xml":
            cap_url = link.get("href")
            break

    author_el = entry.find("atom:author/atom:name", NS)
    source = author_el.text.strip() if author_el is not None and author_el.text else None

    cat_el = entry.find("atom:category", NS)
    category = cat_el.get("term") if cat_el is not None else None

    summary = _atom(entry, "summary")
    alert_id = _stable_id(raw_id)

    return AtomEntry(
        alert_id=alert_id,
        raw_id=raw_id,
        headline=headline,
        issued=issued,
        cap_url=cap_url,
        source=source,
        category=category,
        summary=summary,
    )


def _stable_id(raw_id: str) -> str:
    """
    Derive a stable short ID from a CAP alert's tag URI.

    CAP tag URIs look like: tag:alerts.sshadmin.dev,2024:123456
    We extract the trailing numeric component as the stable ID.
    If extraction fails, derive a deterministic ID from the full URI.
    """
    match = re.search(r":(\w+)$", raw_id)
    if match:
        return match.group(1)[:UUID_TRUNCATE_LENGTH * 2]

    # Deterministic fallback — same input always produces same ID
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_id)).replace("-", "")[:UUID_TRUNCATE_LENGTH * 2]


def _parse_geometry(info: ET.Element) -> Optional[str]:
    """Extract CAP polygon or circle geometry from <area> block."""
    area = info.find("cap:area", NS)
    if area is None:
        area = info.find("area")
    if area is None:
        return None

    polygon = _cap(area, "polygon")
    if polygon and polygon.strip():
        return polygon.strip()

    circle = _cap(area, "circle")
    if circle and circle.strip():
        return circle.strip()

    return None


def _atom(element: ET.Element, tag: str) -> Optional[str]:
    """Get text from an Atom namespace child element."""
    el = element.find(f"atom:{tag}", NS)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _cap(element: Optional[ET.Element], tag: str) -> Optional[str]:
    """Get text from a CAP namespace child element, with no-namespace fallback."""
    if element is None:
        return None
    el = element.find(f"cap:{tag}", NS)
    if el is None:
        el = element.find(tag)  # fallback: no-namespace CAP documents
    if el is not None and el.text:
        return el.text.strip()
    return None
