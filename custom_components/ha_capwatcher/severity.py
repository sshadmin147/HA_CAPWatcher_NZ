"""Severity validation and normalization for NZ-CAP alerts."""

import logging
from typing import Optional

from .const import SEVERITY_INFO, SEVERITY_WATCH, SEVERITY_WARNING, SEVERITY_SEVERE, SEVERITY_EXTREME, SEVERITIES

_LOGGER = logging.getLogger(__name__)

# MetService publishes raw CAP 1.2 severity values; map them to the
# NZ Standard Weather Alert Levels:
#   CAP Minor    → Yellow Watch   (possible, not yet imminent)
#   CAP Moderate → Orange Warning (imminent/occurring, take action)
#   CAP Severe   → Red Warning    (already accepted as 'severe')
#   CAP Extreme  → Red Warning    (already accepted as 'extreme'; NEMA use)
_CAP12_TO_NZCAP: dict[str, str] = {
    "moderate": SEVERITY_WARNING,  # Orange Warning
    "minor": SEVERITY_WATCH,       # Yellow Watch
    "unknown": SEVERITY_INFO,
}


def validate_severity(severity_value: Optional[str]) -> str:
    """
    Validate and normalize a CAP severity value.

    Accepts both NZ-CAP vocabulary (extreme/severe/warning/watch/info) and
    standard CAP 1.2 vocabulary (Moderate/Minor/Unknown), mapping the latter
    to their NZ-CAP equivalents.

    Returns:
        Normalized NZ-CAP severity string.

    Raises:
        ValueError: If severity is None/missing or unrecognized.
    """
    if not severity_value:
        raise ValueError("Missing mandatory CAP severity field")

    normalized = severity_value.lower().strip()

    if normalized in SEVERITIES:
        return normalized

    if normalized in _CAP12_TO_NZCAP:
        return _CAP12_TO_NZCAP[normalized]

    raise ValueError(
        f"Unknown severity value: '{severity_value}'. "
        f"Expected one of: {', '.join(SEVERITIES)}"
    )


def get_severity_color(severity: str) -> dict:
    """
    Get color information for a severity level.

    Args:
        severity: Normalized severity string

    Returns:
        Dict with 'hex' (color code) and 'background' (background color)
    """
    from .const import SEVERITY_COLORS

    if severity not in SEVERITY_COLORS:
        _LOGGER.warning(f"Unknown severity '{severity}', using info color")
        return SEVERITY_COLORS[SEVERITY_INFO]

    return SEVERITY_COLORS[severity]


def get_highest_severity(severities: list[str]) -> str:
    """
    Determine the highest (most urgent) severity from a list.

    Args:
        severities: List of normalized severity strings

    Returns:
        Highest severity, or 'none' if list is empty
    """
    if not severities:
        return "none"

    # Order by priority (first in SEVERITIES list = highest)
    for severity in SEVERITIES:
        if severity in severities:
            return severity

    return "none"
