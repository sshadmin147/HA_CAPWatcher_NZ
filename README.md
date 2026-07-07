# HA-CAPWatcher 🚨

A Home Assistant integration that brings official weather alerts and civil defence notifications directly to your dashboard. Uses the Common Alerting Protocol (CAP) — the same standard used by MetService, NEMA, GeoNet, and government agencies across New Zealand.

## What is CAP?

The **Common Alerting Protocol** is an international standard for distributing emergency alerts. Instead of waiting for a notification to appear, you can see active alerts for your region on your Home Assistant dashboard in real-time, with the same severity classification and information that officials use.

**Alert sources:**
- 🌦️ **MetService** — weather warnings (red/orange/yellow watches)
- 🏘️ **NEMA** — civil defence alerts (evacuations, emergencies)
- 📍 **GeoNet** — earthquake information (magnitude 4.5+)
- 🚨 **Auckland Emergency Management** — Auckland-specific alerts

## Features

### Dashboard Display
- **Standards-compliant** — displays alerts exactly as they appear on MetService.co.nz and official government sources
- **Multi-region** — monitor your home, family members in different regions, or the whole country at once
- **Color-coded severity** — Extreme (red) → Severe → Warning → Watch → Info
- **Live updates** — configurable refresh rate (15 seconds to 5 minutes)
- **Custom card** — HA-CAPWatcher Lovelace card coming in Stage 2

### Automation Support
- **Event entities** — one per feed, selectable in the HA automation UI with no YAML required
- Fires `alert_new` and `alert_expired` events with full alert data (severity, urgency, headline, area)
- Aggregate sensors for alert count, highest severity, and highest urgency — ideal for conditions and dashboards
- Build custom automations: push notifications, sirens, mode changes, and more

### Configuration
- **Easy setup** — one config step in Home Assistant UI, select your region(s)
- **Multiple feeds** — monitor Auckland and Wellington simultaneously, keep them separate or combined
- **Custom feeds** — add your own CAP feed URL if you have a non-standard source
- **Auto-validation** — custom feeds are validated on first poll

## Installation

### Via HACS (recommended)
1. Open Home Assistant → HACS
2. Search for **"HA-CAPWatcher"**
3. Click Install
4. Restart Home Assistant
5. Go to **Settings** → **Devices & Services** → **Create Integration** → **HA-CAPWatcher**
6. Select which feeds to monitor (e.g., "Auckland Enhanced with Earthquakes", "Wellington Region")
7. Done — alerts appear on your dashboard

### Manual Installation
1. Clone this repo into `config/custom_components/ha_capwatcher/`
2. Restart Home Assistant
3. Follow steps 5–7 above

## Configuration

### Select Default Feeds

In the HA integration UI, choose which regional feeds to monitor:

- **All New Zealand** — all MetService + NEMA alerts across NZ
- **By Region** — Northland, Auckland, Waikato, Bay of Plenty, Gisborne, Hawke's Bay, Taranaki, Manawatū-Whanganui, Wellington, Nelson/Tasman, Marlborough, West Coast, Canterbury, Otago, Southland
- **With/Without Earthquakes** — include GeoNet earthquakes (M4.5+) or not
- **Auckland Enhanced** — Auckland-specific alerts from AEM, plus MetService + NEMA + earthquakes

### Add Custom Feeds

In the integration settings, you can add a custom CAP feed URL:
1. Provide the Atom feed URL
2. The integration fetches and validates it
3. If valid, it's added to your feeds
4. Polls start on the next cycle

**Custom feed validation:** The integration checks that your URL returns valid Atom XML with CAP entries containing required fields (severity, urgency, certainty).

### Configure Polling

Choose how often the integration fetches updates:
- **15 seconds** — near real-time (use with 1 feed only)
- **30 seconds** — very responsive
- **45 seconds** — responsive
- **1 minute** — standard (recommended, matches server cache)
- **2 minutes** — relaxed
- **5 minutes** — low-frequency

Each feed can have a different polling interval.

## Usage Examples

### Dashboard Card

After adding the integration, create a dashboard card pointing to your feed device:

```yaml
type: custom:ha_capwatcher_card
device: cap_alerts_nz_auckland
```

Or use the HA UI: **+ Add Card** → **HA-CAPWatcher Card** → select your feed device.

The card displays alerts with NZ-CAP standard colors, severity badges, full descriptions, and affected area maps.

---

## Automations

HA-CAPWatcher is built for automations. Each configured feed gets a stable **event entity** that fires whenever an alert arrives or expires. You can build automations in the HA UI without any YAML.

### Event entities (no YAML required)

Each enabled feed creates one event entity:

| Feed | Entity ID |
|---|---|
| All NZ | `event.official_all_nz_alert_events` |
| Auckland Enhanced | `event.auckland_enhanced_with_earthquakes_alert_events` |
| Wellington Region | `event.region_wellington_alert_events` |
| *(and so on for each enabled feed)* | |

**Setting up an automation in the UI:**

1. Go to **Settings → Automations → Create Automation**
2. Under **When**, add trigger → **Event received**
3. Click **Add target** and select your feed's event entity (e.g. `region_auckland Alert Events`)
4. Set **Event type** to `alert_new` (or `alert_expired`)
5. Under **Then do**, add your action — a notification, a siren, a scene, etc.

That's it. No YAML needed for the trigger.

**Filtering by severity or urgency** — add an **And if** condition:

| Goal | Condition template |
|---|---|
| Only extreme or severe | `{{ trigger.event.data.severity in ['extreme', 'severe'] }}` |
| Only immediate urgency | `{{ trigger.event.data.urgency == 'immediate' }}` |
| Only a specific area | `{{ 'Auckland' in trigger.event.data.area }}` |

#### Event data fields

Both `alert_new` and `alert_expired` events carry:

| Field | Example | Description |
|---|---|---|
| `severity` | `severe` | NZ-CAP severity level |
| `urgency` | `immediate` | CAP urgency level |
| `headline` | `"Severe Wind Warning for Auckland"` | Alert headline |
| `area` | `"Auckland City"` | Affected region |
| `feed` | `region_auckland` | Which feed the alert came from |
| `alert_id` | `urn:oid:2.49.0...` | Unique CAP alert identifier |
| `cap_url` | `https://...` | Link to the full CAP document |

> `alert_expired` only carries `feed` and `alert_id` — the alert data is no longer available.

---

### YAML automation examples

**Push notification on any new alert:**

```yaml
automation:
  - alias: "CAP - New alert notification"
    trigger:
      - platform: event
        event_type: ha_capwatcher_alert_new
        # (leave event_type blank here — it's the HA event bus event,
        #  use the event entity approach above for GUI-based filtering)
```

Prefer the event entity approach above. These YAML examples use the aggregate sensors, which are simpler for state-based conditions.

**Notify when highest severity reaches extreme or severe:**

```yaml
automation:
  - alias: "CAP - Severe or worse alert"
    trigger:
      - platform: state
        entity_id: sensor.highest_severity
        to:
          - "extreme"
          - "severe"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "NZ Weather Alert — {{ trigger.to_state.state | title }}"
          message: "{{ states('sensor.latest_headline') }}"
```

**Trigger when urgency becomes immediate:**

```yaml
automation:
  - alias: "CAP - Immediate urgency alert"
    trigger:
      - platform: state
        entity_id: sensor.highest_urgency
        to: "immediate"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Immediate Action Required"
          message: "{{ states('sensor.latest_headline') }}"
```

**Turn on a siren for extreme alerts:**

```yaml
automation:
  - alias: "CAP - Extreme alert siren"
    trigger:
      - platform: state
        entity_id: sensor.highest_severity
        to: "extreme"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.siren
```

**Alert count goes from zero to something (new alert just arrived):**

```yaml
automation:
  - alias: "CAP - First alert of the day"
    trigger:
      - platform: numeric_state
        entity_id: sensor.alert_count
        above: 0
        from: "0"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "New active alert: {{ states('sensor.latest_headline') }}"
```

---

### Aggregate sensors

Four aggregate sensors are created per integration entry, spanning all enabled feeds. Use these in conditions, dashboards, and state-based triggers.

| Sensor | State values | Description |
|---|---|---|
| `sensor.alert_count` | integer | Total active alerts across all feeds |
| `sensor.highest_severity` | `extreme` / `severe` / `warning` / `watch` / `info` / `none` | Worst severity currently active |
| `sensor.highest_urgency` | `immediate` / `expected` / `future` / `past` / `unknown` / `none` | Most time-critical urgency currently active |
| `sensor.latest_headline` | string | Headline of the highest-priority active alert |

> Entity IDs shown above are the defaults. HA may append a suffix if names conflict — use the entity picker in the UI to find your exact IDs.

## Alert Details

Each alert entity contains:

- **state**: NZ-CAP severity (`extreme` / `severe` / `warning` / `watch` / `info`)
- **headline**: Alert headline (e.g., "Severe Wind Warning")
- **severity**: Same as state — exposed as an attribute for template access
- **urgency**: CAP urgency (`immediate` / `expected` / `future` / `past` / `unknown`)
- **certainty**: CAP certainty (observed, likely, possible, unlikely, unknown)
- **issued**: When the alert was issued (ISO 8601 timestamp)
- **onset**: When the alert becomes active
- **expires**: When the alert expires
- **area**: Affected region/zone
- **description**: Full alert description (MetService/NEMA text)
- **instructions**: What to do (evacuation orders, shelter instructions, etc.)
- **geometry_polygon**: Affected area boundary (GeoJSON polygon)

## Roadmap

### Stage 1 (Current) ✓
- Entity layer with multi-feed support
- Standard CAP compliance
- Rate limit handling
- State persistence on HA restart
- Aggregate sensors (alert count, highest severity, highest urgency, latest headline)
- Event entities per feed — GUI-driven automations with no YAML required
- Config flow with custom feed support

### Stage 2 (Planned)
- Custom HA-CAPWatcher Lovelace card
- Geometry rendering (SVG mini-map of affected area)
- Dismissible alerts in card
- Card configuration options (sort by severity, filter by type, etc.)

### Future Enhancements
- Offline-first caching (fallback if NZAlerts service is down)
- Feed versioning and auto-updates
- Webhook support (alerts push to HA instead of polling)

## Standards & Compliance

This integration strictly follows:
- **NZ-CAP Standard** — Color codes, severity hierarchy, mandatory fields
- **CAP 1.2** (ETSI TS 102 182 V1.2.1) — International alerting standard
- **MetService severity mapping** — Red alerts → Severe, Orange → Warning, Yellow → Watch

All mandatory CAP fields are included. If a feed is missing required data, the alert is skipped with an error message (rather than guessing).

## Performance

- **Polling:** Configurable 15s–5m intervals per feed
- **Rate limits:** 20 requests/minute per IP (enforced via request queuing)
- **Entity count:** Typically 5–20 active alerts per region = minimal performance impact
- **Memory:** ~2KB per alert entity (200–400KB per feed, negligible)
- **State persistence:** Uses HA's built-in restore service, no external database

## Troubleshooting

**No alerts showing?**
1. Check that you've selected a feed in Settings → Devices & Services → HA-CAPWatcher
2. Wait for the first poll (up to 5 minutes depending on polling interval)
3. Check Home Assistant logs for errors: `[custom_components.ha_capwatcher]`

**"Invalid CAP feed URL" error?**
1. Verify the URL returns valid Atom XML (test in browser)
2. Check that the feed contains CAP entries with severity/urgency/certainty fields
3. Ensure the URL is reachable from your HA instance

**Alerts disappear after HA restart?**
- Normal if you have a high polling interval (5m). Alerts are restored, next poll updates them.
- If alerts are missing after 5 minutes, check the integration logs.

**Rate limit 429 errors?**
- Reduce the polling interval or the number of feeds
- The integration automatically backs off to 5-minute intervals on rate limit
- Multiple feeds are queued and polled sequentially to stay within limits

## License

MIT License. See LICENSE file.

## Credits

Built with the Home Assistant Coordinator pattern (standard for polling integrations).

Uses CAP feed data from:
- MetService (New Zealand weather service)
- NEMA (National Emergency Management Agency)
- GeoNet (Earthquake monitoring)
- AEM (Auckland Emergency Management)

## Support

Issues, feature requests, or questions? Open an issue on GitHub.

For NZAlerts service issues, see https://github.com/nz-alerts/nz-alerts

---

**Stay alert. Stay safe.** 🚨
