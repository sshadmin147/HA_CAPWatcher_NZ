"""Coordinator for HA-CAPWatcher CAP feed polling."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BACKOFF_INTERVALS,
    DOMAIN,
    MAX_RETRY_ATTEMPTS,
    RATE_LIMIT_REQUESTS_PER_MINUTE,
)
from .parser import AtomEntry, ParsedAlert, parse_atom_feed, parse_cap_document

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# How many seconds to back off after hitting 429
_RATE_LIMIT_BACKOFF = 300


@dataclass
class FeedData:
    """Data returned by the coordinator to entities on each poll."""

    alerts: dict[str, ParsedAlert] = field(default_factory=dict)
    consecutive_errors: int = 0
    feed_offline: bool = False


class RateLimitQueue:
    """
    Global request queue shared across all Coordinator instances.

    Serialises HTTP requests to stay within 20 req/min per IP.
    All feeds share one queue — stored in hass.data[DOMAIN]["request_queue"].
    """

    def __init__(self, max_per_minute: int = RATE_LIMIT_REQUESTS_PER_MINUTE) -> None:
        self._max_per_minute = max_per_minute
        self._lock = asyncio.Lock()
        self._request_times: list[float] = []

    async def acquire(self) -> None:
        """Block until a request slot is available."""
        async with self._lock:
            now = time.monotonic()
            window_start = now - 60.0

            # Evict timestamps outside the 60-second window
            self._request_times = [t for t in self._request_times if t > window_start]

            if len(self._request_times) >= self._max_per_minute:
                # Wait until the oldest request falls out of the window
                wait_until = self._request_times[0] + 60.0
                delay = wait_until - now
                if delay > 0:
                    _LOGGER.debug("Rate limit: waiting %.1fs for request slot", delay)
                    await asyncio.sleep(delay)
                # Re-evict after waiting
                now = time.monotonic()
                self._request_times = [t for t in self._request_times if t > now - 60.0]

            self._request_times.append(time.monotonic())


class CAPFeedCoordinator(DataUpdateCoordinator):
    """
    Coordinator for a single CAP/Atom feed.

    Lifecycle:
    1. Poll Atom feed → list of active alert IDs + CAP doc URLs
    2. For each new alert ID: fetch CAP document, parse, cache
    3. Remove alerts no longer in the feed (they expired or were cancelled)
    4. Return FeedData to entities

    Alert expiry is detected by absence from the Atom feed — simpler and
    more reliable than parsing datetime strings.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        feed_name: str,
        feed_url: str,
        poll_interval: int,
        session: aiohttp.ClientSession,
        rate_queue: RateLimitQueue,
    ) -> None:
        from datetime import timedelta

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{feed_name}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.feed_name = feed_name
        self.feed_url = feed_url
        self._session = session
        self._rate_queue = rate_queue

        # Cache: alert_id → ParsedAlert (avoids re-fetching CAP docs)
        self._alert_cache: dict[str, ParsedAlert] = {}
        self._consecutive_errors = 0

    async def _async_update_data(self) -> FeedData:
        """
        Fetch and return the current alert state for this feed.
        Called automatically by DataUpdateCoordinator on each poll.
        """
        try:
            data = await self._poll()
            self._consecutive_errors = 0
            return data
        except UpdateFailed:
            self._consecutive_errors += 1
            _LOGGER.warning(
                "[%s] Poll failed (attempt %d/%d)",
                self.feed_name,
                self._consecutive_errors,
                MAX_RETRY_ATTEMPTS,
            )
            raise

    async def _poll(self) -> FeedData:
        """Fetch Atom feed, update cache, return current alerts."""

        # --- Phase 1: fetch Atom feed ---
        atom_xml = await self._fetch(self.feed_url)
        atom_entries = parse_atom_feed(atom_xml, self.feed_name)

        active_ids = {e.alert_id for e in atom_entries}
        entries_by_id = {e.alert_id: e for e in atom_entries}

        # --- Phase 2: fetch CAP docs for new alerts ---
        for alert_id, entry in entries_by_id.items():
            if alert_id not in self._alert_cache:
                alert = await self._fetch_cap_document(entry)
                if alert:
                    self._alert_cache[alert_id] = alert

        # --- Phase 3: evict alerts no longer in feed ---
        evicted = [aid for aid in self._alert_cache if aid not in active_ids]
        for alert_id in evicted:
            _LOGGER.debug("[%s] Alert %s no longer in feed, removing", self.feed_name, alert_id)
            del self._alert_cache[alert_id]

        _LOGGER.debug(
            "[%s] %d active alerts (%d new, %d evicted)",
            self.feed_name,
            len(self._alert_cache),
            len([aid for aid in active_ids if aid in self._alert_cache]),
            len(evicted),
        )

        return FeedData(
            alerts=dict(self._alert_cache),
            consecutive_errors=0,
            feed_offline=False,
        )

    async def _fetch_cap_document(self, entry: AtomEntry) -> ParsedAlert | None:
        """Fetch and parse a single CAP document for a new alert."""
        if not entry.cap_url:
            _LOGGER.warning(
                "[%s] Alert '%s' has no CAP document URL, skipping",
                self.feed_name,
                entry.headline,
            )
            return None

        try:
            cap_xml = await self._fetch(entry.cap_url)
            return parse_cap_document(cap_xml, entry, self.feed_name)
        except UpdateFailed as e:
            _LOGGER.error(
                "[%s] Failed to fetch CAP document for '%s': %s",
                self.feed_name,
                entry.headline,
                e,
            )
            return None

    async def _fetch(self, url: str) -> str:
        """
        Fetch a URL through the shared rate-limit queue.

        Raises:
            UpdateFailed: on HTTP errors, timeouts, or non-200 responses
        """
        await self._rate_queue.acquire()

        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:

                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", _RATE_LIMIT_BACKOFF))
                    _LOGGER.warning(
                        "[%s] Rate limited (429). Backing off %ds.", self.feed_name, retry_after
                    )
                    await asyncio.sleep(retry_after)
                    raise UpdateFailed(f"Rate limited by {url}")

                if resp.status == 410:
                    _LOGGER.debug("[%s] Alert gone (410): %s", self.feed_name, url)
                    raise UpdateFailed(f"Alert expired (410): {url}")

                if resp.status != 200:
                    raise UpdateFailed(
                        f"[{self.feed_name}] HTTP {resp.status} from {url}"
                    )

                return await resp.text()

        except aiohttp.ClientError as e:
            raise UpdateFailed(f"[{self.feed_name}] Connection error: {e}") from e
        except TimeoutError as e:
            raise UpdateFailed(f"[{self.feed_name}] Timeout fetching {url}") from e

    @property
    def is_feed_offline(self) -> bool:
        """True when consecutive errors exceed the retry threshold."""
        return self._consecutive_errors >= MAX_RETRY_ATTEMPTS

    @property
    def active_alert_count(self) -> int:
        """Number of currently cached active alerts."""
        return len(self._alert_cache)
