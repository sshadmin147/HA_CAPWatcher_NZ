"""Tests for feeds_loader — YAML loading, validation, filtering, merging."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from custom_components.ha_capwatcher.feeds_loader import (
    get_enabled_feeds,
    load_default_feeds,
    merge_feeds,
    validate_feed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feed(
    name: str = "my_feed",
    url: str = "https://alerts.sshadmin.dev/cap/feeds/official/all-nz",
    enabled: bool = True,
    **extra,
) -> dict:
    return {"name": name, "url": url, "enabled": enabled, **extra}


# ---------------------------------------------------------------------------
# load_default_feeds — reads the actual bundled YAML
# ---------------------------------------------------------------------------

class TestLoadDefaultFeeds:
    def test_returns_a_list(self):
        feeds = load_default_feeds()
        assert isinstance(feeds, list)

    def test_list_is_non_empty(self):
        feeds = load_default_feeds()
        assert len(feeds) > 0

    def test_every_entry_is_a_dict(self):
        feeds = load_default_feeds()
        for feed in feeds:
            assert isinstance(feed, dict), f"Expected dict, got {type(feed)}: {feed}"

    def test_every_entry_has_required_keys(self):
        feeds = load_default_feeds()
        for feed in feeds:
            assert "name" in feed, f"Missing 'name' in {feed}"
            assert "url" in feed, f"Missing 'url' in {feed}"
            assert "enabled" in feed, f"Missing 'enabled' in {feed}"

    def test_every_entry_is_valid(self):
        feeds = load_default_feeds()
        for feed in feeds:
            errors = validate_feed(feed)
            assert errors == [], f"Feed '{feed.get('name')}' has validation errors: {errors}"

    def test_official_all_nz_is_enabled_by_default(self):
        feeds = load_default_feeds()
        names = {f["name"]: f for f in feeds}
        assert "official_all_nz" in names
        assert names["official_all_nz"]["enabled"] is True

    def test_only_one_feed_enabled_by_default(self):
        feeds = load_default_feeds()
        enabled = [f for f in feeds if f.get("enabled") is True]
        assert len(enabled) == 1, (
            f"Expected exactly 1 feed enabled by default, got {len(enabled)}: "
            f"{[f['name'] for f in enabled]}"
        )

    def test_all_15_regions_present(self):
        feeds = load_default_feeds()
        names = {f["name"] for f in feeds}
        expected_regions = {
            "region_northland", "region_auckland", "region_waikato",
            "region_bay_of_plenty", "region_gisborne", "region_hawkes_bay",
            "region_taranaki", "region_manawatu_whanganui", "region_wellington",
            "region_nelson_tasman", "region_marlborough", "region_west_coast",
            "region_canterbury", "region_otago", "region_southland",
        }
        missing = expected_regions - names
        assert not missing, f"Missing regional feeds: {missing}"

    def test_returns_empty_list_on_missing_file(self):
        with patch(
            "custom_components.ha_capwatcher.feeds_loader.DEFAULT_FEEDS_PATH",
            Path("/nonexistent/path/feeds.yaml"),
        ):
            result = load_default_feeds()
        assert result == []

    def test_returns_empty_list_on_malformed_yaml(self):
        with patch(
            "custom_components.ha_capwatcher.feeds_loader.yaml.safe_load",
            side_effect=yaml.YAMLError("bad yaml"),
        ):
            result = load_default_feeds()
        assert result == []

    def test_returns_empty_list_when_feeds_key_missing(self):
        with patch(
            "custom_components.ha_capwatcher.feeds_loader.yaml.safe_load",
            return_value={"other": "data"},
        ):
            result = load_default_feeds()
        assert result == []


# ---------------------------------------------------------------------------
# validate_feed
# ---------------------------------------------------------------------------

class TestValidateFeed:
    def test_valid_feed_has_no_errors(self):
        assert validate_feed(_feed()) == []

    def test_valid_feed_with_label_and_comments(self):
        feed = _feed(label="My Feed", description="A description")
        assert validate_feed(feed) == []

    def test_missing_name(self):
        feed = {"url": "https://example.com/feed", "enabled": True}
        errors = validate_feed(feed)
        assert any("name" in e for e in errors)

    def test_empty_name(self):
        errors = validate_feed(_feed(name=""))
        assert any("name" in e for e in errors)

    def test_name_with_uppercase(self):
        errors = validate_feed(_feed(name="MyFeed"))
        assert any("invalid" in e.lower() or "name" in e.lower() for e in errors)

    def test_name_with_hyphens_rejected(self):
        errors = validate_feed(_feed(name="my-feed"))
        assert errors  # hyphens not allowed

    def test_name_starting_with_digit_rejected(self):
        errors = validate_feed(_feed(name="1feed"))
        assert errors

    def test_name_with_spaces_rejected(self):
        errors = validate_feed(_feed(name="my feed"))
        assert errors

    def test_missing_url(self):
        feed = {"name": "my_feed", "enabled": True}
        errors = validate_feed(feed)
        assert any("url" in e for e in errors)

    def test_url_without_http_scheme(self):
        errors = validate_feed(_feed(url="ftp://example.com/feed"))
        assert any("http" in e.lower() for e in errors)

    def test_url_relative_path_rejected(self):
        errors = validate_feed(_feed(url="/cap/feeds/official/all-nz"))
        assert errors

    def test_http_url_accepted(self):
        assert validate_feed(_feed(url="http://example.com/feed")) == []

    def test_https_url_accepted(self):
        assert validate_feed(_feed(url="https://alerts.sshadmin.dev/cap/feeds/official/all-nz")) == []

    def test_missing_enabled(self):
        feed = {"name": "my_feed", "url": "https://example.com/feed"}
        errors = validate_feed(feed)
        assert any("enabled" in e for e in errors)

    def test_enabled_as_string_rejected(self):
        errors = validate_feed(_feed(enabled="yes"))  # type: ignore[arg-type]
        assert any("enabled" in e for e in errors)

    def test_enabled_as_int_rejected(self):
        errors = validate_feed(_feed(enabled=1))  # type: ignore[arg-type]
        assert any("enabled" in e for e in errors)

    def test_non_dict_feed_returns_error(self):
        errors = validate_feed("not a dict")  # type: ignore[arg-type]
        assert errors


# ---------------------------------------------------------------------------
# get_enabled_feeds
# ---------------------------------------------------------------------------

class TestGetEnabledFeeds:
    def test_returns_only_enabled_feeds(self):
        feeds = [_feed("a", enabled=True), _feed("b", enabled=False)]
        result = get_enabled_feeds(feeds)
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_returns_empty_when_all_disabled(self):
        feeds = [_feed("a", enabled=False), _feed("b", enabled=False)]
        assert get_enabled_feeds(feeds) == []

    def test_returns_empty_when_list_is_empty(self):
        assert get_enabled_feeds([]) == []

    def test_skips_invalid_feeds(self):
        feeds = [
            {"name": "bad", "enabled": True},  # missing url
            _feed("good", enabled=True),
        ]
        result = get_enabled_feeds(feeds)
        assert len(result) == 1
        assert result[0]["name"] == "good"

    def test_all_valid_enabled_feeds_returned(self):
        feeds = [_feed("a"), _feed("b"), _feed("c")]
        assert len(get_enabled_feeds(feeds)) == 3

    def test_real_default_feeds_returns_one_enabled(self):
        feeds = load_default_feeds()
        enabled = get_enabled_feeds(feeds)
        assert len(enabled) == 1
        assert enabled[0]["name"] == "official_all_nz"


# ---------------------------------------------------------------------------
# merge_feeds
# ---------------------------------------------------------------------------

class TestMergeFeeds:
    def test_custom_overrides_default_by_name(self):
        default = [_feed("a", enabled=False)]
        custom = [_feed("a", enabled=True)]
        result = merge_feeds(default, custom)
        assert len(result) == 1
        assert result[0]["enabled"] is True

    def test_new_custom_feed_appended(self):
        default = [_feed("a")]
        custom = [_feed("b")]
        result = merge_feeds(default, custom)
        names = [f["name"] for f in result]
        assert "a" in names
        assert "b" in names
        assert len(result) == 2

    def test_default_feeds_order_preserved(self):
        default = [_feed("a"), _feed("b"), _feed("c")]
        result = merge_feeds(default, [])
        assert [f["name"] for f in result] == ["a", "b", "c"]

    def test_empty_custom_returns_defaults_unchanged(self):
        default = [_feed("a"), _feed("b")]
        result = merge_feeds(default, [])
        assert result == default

    def test_empty_defaults_returns_custom(self):
        custom = [_feed("x"), _feed("y")]
        result = merge_feeds([], custom)
        assert [f["name"] for f in result] == ["x", "y"]

    def test_multiple_custom_overrides(self):
        default = [_feed("a", enabled=False), _feed("b", enabled=False)]
        custom = [_feed("a", enabled=True), _feed("b", enabled=True)]
        result = merge_feeds(default, custom)
        assert all(f["enabled"] for f in result)

    def test_invalid_entries_without_name_ignored_in_merge(self):
        default = [_feed("a")]
        custom = [{"url": "https://example.com", "enabled": True}]  # no name
        result = merge_feeds(default, custom)
        assert len(result) == 1
        assert result[0]["name"] == "a"
