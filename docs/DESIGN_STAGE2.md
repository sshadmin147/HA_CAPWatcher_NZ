# Design: HA-CAPWatcher — Stage 2 Lovelace Card

Generated: 2026-06-26
Repo: sshadmin/HA_CAPWatcher_NZ (Stage 1 source)
Stage 2 Repo: **separate repository** — `lovelace-ha-capwatcher` (to be created)
Status: DRAFT — ready for implementation planning
Depends on: Stage 1 complete and live (confirmed 2026-06-26)

---

## Overview

Stage 1 delivers the integration layer — CAP feeds parsed, entities created, severity mapped, aggregate helpers working. Stage 2 is the **presentation layer**: a custom Lovelace card that reads those entities and renders them as a standards-compliant, color-coded alert dashboard inside Home Assistant.

The card lives in a **separate HACS repository** because:
- Lovelace cards are distributed as JavaScript resources, not Python integrations
- They have different versioning, CI, and release pipelines
- Users may want the card without the integration (e.g. if they run a different CAP backend)
- HACS treats them as separate categories: Integration vs. Frontend

---

## Problem the Card Solves

Stage 1 entities are functional but raw. In Developer Tools → States, you can see them working. But for real household use:
- You can't scan alert severity at a glance in the default HA entity cards
- The NZ-CAP color coding (Red/Orange/Yellow) is lost — everything looks the same
- There's no way to read the full description, instructions, or affected area without drilling into entity details
- When there are no alerts, the entity list just shows unavailable sensors — not a clear "all clear" state

The card closes that gap: a single Lovelace element that presents all active alerts from a configured HA-CAPWatcher entry with the correct NZ-CAP visual language.

---

## What Stage 2 Delivers

### Core (MVP)

- **Alert list view** — one row per active alert, color-coded by severity (Red/Orange/Yellow/Info)
- **Severity badge** — colored chip showing extreme / severe / warning / watch / info
- **Expandable detail panel** — click an alert to expand: description, instructions, issued/expires/onset timestamps, area, source, cap_url link
- **No-alerts state** — explicit "No active alerts" display with a green/neutral indicator
- **Live updates** — card reactively updates when HA state changes (no page refresh needed)
- **Card config** — YAML configuration: which integration entry to watch, sort order, max alerts shown

### Extended (same stage, post-MVP)

- **Geometry mini-map** — inline SVG rendering of the `geometry_polygon` attribute showing the affected area boundary on a simple NZ coastline outline
- **Dismissible alerts** — "acknowledge" button per alert; dismissed alerts are hidden until they change state (stored in browser localStorage, not HA state)
- **Filter options** — hide alerts below a configured severity threshold (e.g. only show `warning` and above)
- **Header summary** — compact summary line above the list: "3 active alerts — highest: warning" using the aggregate helper sensors

---

## Entity Contract (What the Card Reads from Stage 1)

The card communicates exclusively through HA entity state and attributes. No direct API calls, no custom websocket endpoints.

### Individual alert entities
```
entity_id: sensor.ha_capwatcher_<entry>_<8char_id>
state:      warning | watch | severe | extreme | info
attributes:
  headline:             "Heavy Rain Warning - Orange"
  severity:             "warning"
  urgency:              "immediate"
  certainty:            "likely"
  issued:               "2026-06-26T05:49:32Z"
  onset:                "2026-06-26T05:00:00Z"
  expires:              "2026-06-27T06:00:00Z"
  area:                 "The Tararua Range, Wairarapa south of Masterton, and Wellington"
  description:          "Expect 60 to 90 mm of rain..."
  instructions:         "Action: Clear your drains and gutters..."
  cap_url:              "https://alerts.metservice.com/cap/alert?id=..."
  source:               "Meteorological Service of New Zealand Limited"
  category:             "Met"
  feed_name:            "official_all_nz"
  severity_color:       "#FF8918"
  severity_background:  "#fef3e2"
  geometry_polygon:     "<polygon coords or null>"
```

### Aggregate helper entities (for card header)
```
sensor.ha_capwatcher_<entry>_alert_count       state: "3"
sensor.ha_capwatcher_<entry>_highest_severity  state: "warning"
sensor.ha_capwatcher_<entry>_latest_headline   state: "Heavy Rain Warning - Orange"
```

### Entity discovery strategy

The card accepts one config value: `entry` (the HA-CAPWatcher config entry slug, e.g. `ha_capwatcher`). From that it:
1. Reads the three aggregate sensors directly (known entity IDs)
2. Iterates `hass.states` to find all entities matching `sensor.ha_capwatcher_<entry>_*` that are NOT one of the three aggregates
3. Filters to only entities whose `state` is a known severity value (excludes unavailable, unknown)

This means no additional config needed — the card self-discovers alerts from the entry name alone.

---

## Architecture

### Technology

| Concern | Choice | Reason |
|---|---|---|
| Card framework | LitElement (HA standard) | Required by HA, reactive properties, shadow DOM |
| Build toolchain | Vite + TypeScript | Fast builds, type safety, standard in HA card ecosystem |
| Geometry rendering | Inline SVG (no library) | Lightweight; NZ coastline as embedded path; no network dependency |
| Dismissal storage | `window.localStorage` | Per-browser, no HA state pollution; clears on alert state change |
| Distribution | HACS (Frontend category) | Standard for Lovelace cards |
| Testing | Web Test Runner + Mocha | No HA installation needed; test as web components |

### Repo structure

```
lovelace-ha-capwatcher/
├── src/
│   ├── ha-capwatcher-card.ts        # Main card element
│   ├── ha-capwatcher-editor.ts      # Visual config editor (HACS requirement for gui-friendly cards)
│   ├── components/
│   │   ├── alert-row.ts             # Single alert row (collapsed)
│   │   ├── alert-detail.ts          # Expanded alert panel
│   │   ├── severity-badge.ts        # Color chip
│   │   ├── no-alerts-state.ts       # Empty state display
│   │   └── nz-minimap.ts            # SVG geometry renderer
│   ├── types/
│   │   ├── ha-types.ts              # HA hass object, entity state interfaces
│   │   └── cap-alert.ts             # Typed alert entity shape
│   ├── utils/
│   │   ├── severity.ts              # Color/label lookups
│   │   ├── entity-filter.ts         # Alert discovery from hass.states
│   │   └── dismissal.ts             # localStorage read/write
│   └── styles/
│       └── nz-cap-colors.css        # NZ-CAP color variables
├── dist/
│   └── ha-capwatcher-card.js        # Built output (committed for HACS)
├── tests/
│   ├── severity.test.ts
│   ├── entity-filter.test.ts
│   └── dismissal.test.ts
├── hacs.json
├── package.json
└── README.md
```

### Component tree

```
<ha-capwatcher-card>
  ├── header (summary bar, if config.show_header = true)
  │   ├── alert count badge
  │   └── highest severity chip
  │
  ├── [no alerts state]           ← shown when alert_count = 0
  │   └── <no-alerts-state>
  │
  └── [alert list]                ← shown when alert_count > 0
      └── <alert-row> × N
          ├── <severity-badge>
          ├── headline text
          ├── area text
          ├── issued/expires timestamps
          └── [expanded: <alert-detail>]
              ├── description
              ├── instructions
              ├── timestamps (issued, onset, expires)
              ├── source + cap_url link
              └── <nz-minimap> (if geometry_polygon present)
```

---

## Visual Design

### NZ-CAP color standard

All colors match Stage 1 exactly (same constants, copied across repos):

| Severity | Badge color | Row background | Label |
|---|---|---|---|
| extreme  | `#9b1c1c` | `#f9e0e0` | EXTREME |
| severe   | `#FF181E` | `#fde8e8` | SEVERE |
| warning  | `#FF8918` | `#fef3e2` | WARNING |
| watch    | `#FFEB18` | `#e8f0fd` | WATCH |
| info     | `#8b95a1` | transparent | INFO |

### Alert row layout (collapsed)

```
┌─────────────────────────────────────────────────────────┐
│ [WARNING]  Heavy Rain Warning - Orange          ↓ expand │
│            Tararua Range, Wairarapa, Wellington          │
│            Issued 5:49 PM · Expires 27 Jun 6:00 AM      │
└─────────────────────────────────────────────────────────┘
```

- Left border = 4px solid severity color
- Badge = pill/chip with severity color background + white text
- Area and timestamps in secondary text color (HA var `--secondary-text-color`)
- Expand/collapse chevron on right

### Alert detail panel (expanded)

```
┌─────────────────────────────────────────────────────────┐
│ [WARNING]  Heavy Rain Warning - Orange          ↑ close  │
│            Tararua Range, Wairarapa, Wellington          │
│            Issued 5:49 PM · Onset 5:00 PM               │
│            Expires 27 Jun 6:00 AM                        │
│ ─────────────────────────────────────────────────────── │
│ Expect 60 to 90 mm of rain on top of what has already   │
│ fallen, especially about the ranges...                   │
│                                                          │
│ Action: Clear your drains and gutters to prepare for     │
│ heavy rain. Avoid low-lying areas and drive cautiously.  │
│ ─────────────────────────────────────────────────────── │
│ [NZ mini-map with affected area polygon highlighted]     │
│ ─────────────────────────────────────────────────────── │
│ Source: Meteorological Service of New Zealand Limited    │
│ Official alert →  [link]          [Acknowledge ✓]        │
└─────────────────────────────────────────────────────────┘
```

### No-alerts state

```
┌─────────────────────────────────────────────────────────┐
│  ✓  No active alerts                                     │
│     Last checked: 8:32 PM                                │
└─────────────────────────────────────────────────────────┘
```

Green checkmark, neutral background, timestamp from aggregate sensor's last_updated.

---

## Card Configuration (YAML)

```yaml
type: custom:ha-capwatcher-card
entry: ha_capwatcher          # Required — HA-CAPWatcher config entry slug
title: "NZ Weather Alerts"    # Optional — card title (default: "Active Alerts")
show_header: true             # Optional — show summary bar (default: true)
max_alerts: 10                # Optional — max alerts shown (default: all)
min_severity: watch           # Optional — hide alerts below this level (default: info)
sort_by: severity             # Optional — severity | issued | feed_name (default: severity)
show_geometry: true           # Optional — show mini-map in expanded view (default: true)
show_acknowledge: true        # Optional — show dismiss button (default: true)
```

### Visual config editor

The card provides a `getConfigElement()` editor (LitElement component) so users can configure it via the Lovelace UI without editing YAML. Fields:
- Entry slug (text, with helper text explaining where to find it)
- Title (text)
- Min severity (dropdown: info / watch / warning / severe / extreme)
- Sort by (dropdown)
- Show header / show geometry / show acknowledge (toggles)

---

## Geometry Mini-Map

The `geometry_polygon` attribute contains a coordinate string from the CAP `<circle>` or `<polygon>` element. For Stage 2, the mini-map renders using:

1. **NZ coastline** — an embedded SVG path (simplified GeoJSON → SVG path, ~8KB, no external fetch). The NZ outline is hardcoded as a `<path>` element in `nz-minimap.ts`.

2. **Alert polygon** — the `geometry_polygon` value is parsed as either:
   - Circle: `lat,lon radius` → rendered as SVG `<circle>`
   - Polygon: `lat1,lon1 lat2,lon2 ...` → rendered as SVG `<polygon>`

3. **Projection** — simple equirectangular (lat/lon directly to x/y with a NZ bounding box). Accurate enough for a mini-map; no Mercator needed at this scale.

4. **Fallback** — if `geometry_polygon` is null or unparseable, the mini-map section is hidden entirely (no error state shown to user).

5. **Colors** — affected area fill = severity_background with 60% opacity; border = severity_color.

The coastline SVG path will be generated once from NZ GeoJSON (Stats NZ or LINZ open data) and embedded in the source. It does not load at runtime.

---

## Dismissal Behaviour

When a user clicks "Acknowledge" on an alert:
- The alert's entity_id + current state value are stored in `localStorage['ha_capwatcher_dismissed']`
- The alert row is hidden from the card
- If the alert's severity changes (e.g. watch → warning), the stored entry is stale and the alert reappears automatically
- If the alert entity disappears (expired), the stored entry is garbage-collected on next card render
- Dismissals are per-browser. They are not shared between HA users.
- A dismissed alert count is shown in the header: "2 active (1 acknowledged)"

---

## Reactivity Model

LitElement + HA's `hass` property injection:

```typescript
@property({ attribute: false }) hass!: HomeAssistant;

// hass is updated by HA whenever any entity state changes.
// LitElement re-renders whenever hass changes.
// We filter to only our entities inside render() to avoid unnecessary work.

get _alerts(): AlertEntity[] {
  return filterAlertEntities(this.hass.states, this._config.entry);
}
```

No subscriptions to manage, no polling, no WebSocket handling — HA injects the updated `hass` object and LitElement diffs the render. This is the standard HA card pattern.

---

## HACS Distribution

### hacs.json (card repo root)
```json
{
  "name": "HA-CAPWatcher Card",
  "render_readme": true
}
```

### Lovelace resource registration

HACS automatically registers the card JS as a Lovelace resource after install. No manual `configuration.yaml` edit required for HACS users.

The built `dist/ha-capwatcher-card.js` is committed to the repo (standard for Lovelace cards). HACS downloads it directly from GitHub. No build step required on the user's machine.

### Release process

1. Bump version in `package.json`
2. Run `npm run build` → updates `dist/ha-capwatcher-card.js`
3. Commit dist file
4. Create GitHub release tag (e.g. `v0.2.0`)
5. HACS auto-detects the release and notifies users of the update

---

## Dependencies Between Stage 1 and Stage 2

| Stage 1 provides | Stage 2 consumes |
|---|---|
| `sensor.ha_capwatcher_<entry>_<id>` entities | Alert discovery via `hass.states` filter |
| `state` = severity string | Severity color lookup |
| `attributes.headline` | Alert row title |
| `attributes.area` | Alert row subtitle |
| `attributes.description` | Expanded panel body |
| `attributes.instructions` | Expanded panel action text |
| `attributes.issued/onset/expires` | Timestamp display |
| `attributes.severity_color` | Badge and border color (passed directly from Stage 1, no recalculation) |
| `attributes.severity_background` | Row and mini-map fill color |
| `attributes.geometry_polygon` | Mini-map rendering |
| `attributes.cap_url` | "Official alert →" link |
| `attributes.source` | Source attribution line |
| `sensor.ha_capwatcher_<entry>_alert_count` | Header badge count |
| `sensor.ha_capwatcher_<entry>_highest_severity` | Header severity chip |
| `sensor.ha_capwatcher_<entry>_latest_headline` | Header headline (optional) |

**Stage 2 has no runtime dependency on Stage 1's Python code.** It only reads HA entity state. This means:
- The card works with any future version of Stage 1 that maintains the same entity contract
- The card could theoretically work with a different CAP integration that produces the same entity shape

---

## What's NOT in Stage 2

| Feature | Status | Notes |
|---|---|---|
| Sound/siren alerts | Out — this is an automation concern, not a card concern |
| Push notifications | Out — handled by HA notify services + automations |
| Alert history/log | Out — HA's history panel handles this |
| Feed management in card | Out — handled by Stage 1 config flow |
| Multi-entry view | Out (Stage 3?) — one card per entry for now |
| GeoNet earthquake overlay | Out (Stage 3?) — requires different geometry handling |
| Offline mode/caching | Out — HA handles service resilience |

---

## Open Questions for Stage 2

1. **NZ coastline source** — Use Stats NZ simplified boundary or generate from LINZ data? Stats NZ is likely sufficient for a mini-map. Needs a license check (Stats NZ uses Creative Commons Attribution 4.0, which is fine).

2. **Card repo name** — `lovelace-ha-capwatcher` (common convention for HA Lovelace cards) or `HA_CAPWatcher_Card_NZ`? Convention favors `lovelace-ha-capwatcher`.

3. **Bundled vs unbundled** — Should `dist/` be committed or generated via CI and attached to releases? Committing to dist is the HA community norm for Lovelace cards; it simplifies HACS distribution.

4. **TypeScript strictness** — Strict mode recommended. Type the `HomeAssistant` interface from `custom-card-helpers` package (standard in HA card development).

5. **Visual config editor scope** — Minimum viable editor (entry slug + title only) or full editor (all config options)? Full editor is better UX but doubles the frontend code. Recommend MVP editor for launch, full editor post-launch.

6. **Acknowledged alert persistence** — `localStorage` means dismissals are per-browser and not synced between devices/users. Is that acceptable, or should acknowledgements be stored as HA input_boolean entities? localStorage is simpler and doesn't pollute HA state; recommend it for Stage 2.

---

## Success Criteria

- Card renders all active alerts from a configured HA-CAPWatcher entry in real time
- Severity colors match NZ Standard Weather Alert Levels exactly (same hex values as Stage 1)
- No-alerts state is clearly distinguishable from a loading/error state
- Expanded detail shows all CAP mandatory fields
- Mini-map renders affected area for alerts with geometry data
- Dismissed alerts are hidden until severity changes or alert expires
- Card config is minimal (entry slug required; everything else optional with sensible defaults)
- Card installs via HACS with no manual resource registration
- Works on HA 2024.1+ (Chrome, Firefox, Safari — HA's supported browser matrix)

---

## Implementation Order

1. **Repo setup** — create `lovelace-ha-capwatcher`, init Vite + TypeScript + LitElement scaffold, add HACS json, basic README
2. **Types** — define `CAPAlertEntity` TypeScript interface mirroring Stage 1 attribute contract
3. **Entity filter utility** — `filterAlertEntities(states, entry)` — pure function, fully testable
4. **Severity utility** — `getSeverityColor(severity)`, `getSeverityLabel(severity)` — mirrors Stage 1 `severity.py` constants
5. **Alert row component** — collapsed view with severity badge, headline, area, timestamps
6. **Alert detail component** — expanded panel with all fields
7. **No-alerts state component** — clear empty state
8. **Main card element** — wires hass → filter → render, handles card config, registers as custom element
9. **Visual config editor** — entry slug + title at minimum
10. **Build pipeline** — Vite config, npm scripts, dist commit workflow
11. **Mini-map** — NZ coastline SVG + polygon rendering (can ship after initial release)
12. **Dismissal** — localStorage logic + acknowledge button
13. **HACS release** — tag v0.2.0, submit to HACS default store

---

## Effort Estimate

| Section | Estimate |
|---|---|
| Repo + scaffold + types | 0.5 day |
| Entity filter + severity utils (with tests) | 0.5 day |
| Alert row + detail components | 1.5 days |
| Main card + config editor | 1 day |
| Build pipeline + HACS distribution | 0.5 day |
| Mini-map (coastline SVG + polygon render) | 1.5 days |
| Dismissal + header summary | 0.5 day |
| QA on real HA instance | 1 day |
| **Total** | **~7 days** |
