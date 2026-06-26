"""Load and validate CAP feed definitions from YAML."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

_LOGGER = logging.getLogger(__name__)

DEFAULT_FEEDS_PATH = Path(__file__).parent / "default_feeds.yaml"

# Feed names must be lowercase identifiers (letters, digits, underscores).
# Used directly in coordinator names and HA entity unique_ids.
_VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def load_default_feeds() -> list[dict[str, Any]]:
    """
    Load the bundled default_feeds.yaml.

    Returns the full list of feed dicts (both enabled and disabled).
    Returns an empty list on any parse failure.
    """
    try:
        with DEFAULT_FEEDS_PATH.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict) or "feeds" not in data:
            _LOGGER.error("default_feeds.yaml is missing a top-level 'feeds' key")
            return []
        feeds = data["feeds"]
        if not isinstance(feeds, list):
            _LOGGER.error("'feeds' in default_feeds.yaml must be a list")
            return []
        return feeds
    except FileNotFoundError:
        _LOGGER.error("default_feeds.yaml not found at %s", DEFAULT_FEEDS_PATH)
        return []
    except yaml.YAMLError as exc:
        _LOGGER.error("Failed to parse default_feeds.yaml: %s", exc)
        return []


def validate_feed(feed: dict[str, Any]) -> list[str]:
    """
    Validate a single feed dict.

    Returns a list of human-readable error strings.
    An empty list means the feed is valid.
    """
    if not isinstance(feed, dict):
        return ["Feed entry must be a mapping, got %s" % type(feed).__name__]

    errors: list[str] = []

    name = feed.get("name")
    if not name:
        errors.append("Feed is missing 'name'")
    elif not isinstance(name, str):
        errors.append(f"Feed 'name' must be a string, got {type(name).__name__}")
    elif not _VALID_NAME_RE.match(name):
        errors.append(
            f"Feed name '{name}' is invalid — use lowercase letters, digits, "
            "and underscores only, starting with a letter"
        )

    url = feed.get("url")
    if not url:
        errors.append(f"Feed '{name or '<unnamed>'}' is missing 'url'")
    elif not isinstance(url, str):
        errors.append(f"Feed '{name}' 'url' must be a string")
    elif not url.startswith(("http://", "https://")):
        errors.append(
            f"Feed '{name}' URL must start with http:// or https://, got: {url!r}"
        )

    if "enabled" not in feed:
        errors.append(f"Feed '{name or '<unnamed>'}' is missing 'enabled'")
    elif not isinstance(feed["enabled"], bool):
        errors.append(
            f"Feed '{name}' 'enabled' must be true or false, got: {feed['enabled']!r}"
        )

    return errors


def get_enabled_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filter to enabled feeds, skipping any that fail validation.

    Logs a warning for each invalid or disabled feed that had errors.
    Returns only feeds with enabled: true and no validation errors.
    """
    enabled: list[dict[str, Any]] = []
    for feed in feeds:
        errors = validate_feed(feed)
        if errors:
            name = feed.get("name", "<unnamed>") if isinstance(feed, dict) else "<unnamed>"
            _LOGGER.warning(
                "Skipping invalid feed '%s': %s", name, "; ".join(errors)
            )
            continue
        if feed["enabled"]:
            enabled.append(feed)
    return enabled


def merge_feeds(
    default: list[dict[str, Any]],
    custom: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge user-provided custom feeds over the defaults.

    Custom feeds with the same name override the default entry.
    Custom feeds with new names are appended.
    Order: defaults first (in their original order), then new custom-only feeds.
    """
    merged: dict[str, dict[str, Any]] = {f["name"]: f for f in default if isinstance(f, dict) and "name" in f}
    for feed in custom:
        if isinstance(feed, dict) and "name" in feed:
            merged[feed["name"]] = feed
    return list(merged.values())
