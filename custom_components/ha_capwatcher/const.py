"""Constants for HA-CAPWatcher integration."""

# NZ-CAP Severity Levels
# Source: NZ-CAP Standard, used consistently across MetService, NEMA, GeoNet feeds
# Ordered by priority (highest first)
SEVERITY_EXTREME = "extreme"
SEVERITY_SEVERE = "severe"
SEVERITY_WARNING = "warning"
SEVERITY_WATCH = "watch"
SEVERITY_INFO = "info"

SEVERITIES = [
    SEVERITY_EXTREME,
    SEVERITY_SEVERE,
    SEVERITY_WARNING,
    SEVERITY_WATCH,
    SEVERITY_INFO,
]

# Severity fallback: if a CAP alert doesn't have severity (shouldn't happen),
# fail loudly and skip the alert. Do NOT infer or default to 'info'.
SEVERITY_FALLBACK_BEHAVIOR = "fail_loudly"

# NZ-CAP Color Mapping
# These hex codes are standardized in the NZ-CAP spec and used across all sources
# (MetService, NEMA, GeoNet via NZAlerts)
SEVERITY_COLORS = {
    SEVERITY_EXTREME: {"hex": "#9b1c1c", "background": "#f9e0e0"},  # NEMA: life-threatening
    SEVERITY_SEVERE: {"hex": "#FF181E", "background": "#fde8e8"},    # MetService: Red
    SEVERITY_WARNING: {"hex": "#FF8918", "background": "#fef3e2"},   # MetService: Orange
    SEVERITY_WATCH: {"hex": "#FFEB18", "background": "#e8f0fd"},     # MetService: Yellow
    SEVERITY_INFO: {"hex": "#8b95a1", "background": None},           # General information
}

# Integration name and domain
DOMAIN = "ha_capwatcher"
INTEGRATION_NAME = "HA-CAPWatcher"

# Config keys
CONF_FEEDS = "feeds"
CONF_POLLING_INTERVAL = "polling_interval"

# Polling presets (in seconds)
POLLING_PRESETS = {
    "15_seconds": 15,
    "30_seconds": 30,
    "45_seconds": 45,
    "1_minute": 60,
    "2_minutes": 120,
    "5_minutes": 300,
}

# Rate limit enforcement
RATE_LIMIT_REQUESTS_PER_MINUTE = 20
RATE_LIMIT_QUEUE_SERIALIZATION = True  # Serialize feeds to stay within limit

# Entity naming
ENTITY_ID_PREFIX = "cap_alerts_nz"
UUID_TRUNCATE_LENGTH = 8  # Use first 8 chars of alert UUID for entity ID

# Error handling
MAX_RETRY_ATTEMPTS = 5
BACKOFF_INTERVALS = [5, 10, 30, 120, 300]  # seconds: 5s, 10s, 30s, 2m, 5m

# Attributes (all mandatory NZ-CAP fields)
ATTR_SEVERITY = "severity"
ATTR_URGENCY = "urgency"
ATTR_CERTAINTY = "certainty"
ATTR_ISSUED = "issued"
ATTR_ONSET = "onset"
ATTR_EXPIRES = "expires"
ATTR_AREA = "area"
ATTR_DESCRIPTION = "description"
ATTR_INSTRUCTIONS = "instructions"
ATTR_GEOMETRY = "geometry_polygon"  # Stored separately to avoid attribute bloat
