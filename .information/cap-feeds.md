# NZ Alerts — Public CAP Feed Reference

All feeds are unauthenticated and publicly accessible. No API key required.

## Rate limiting

- **20 requests per minute per IP address**
- Responses are **cached server-side for 60 seconds**
- A client polling once per minute will never hit the rate limit and always receives a fresh response
- Exceeding the limit returns HTTP 429

## Response format

All feeds return `Content-Type: application/atom+xml; charset=UTF-8` with the following HTTP cache headers:

```
Cache-Control: public, max-age=60
Last-Modified: <RFC 7231 date of most recent alert>
```

Individual alert documents return `Content-Type: application/cap+xml; charset=UTF-8`.

---

## Feeds

### 1. Official NZ — All New Zealand

```
GET /cap/feeds/official/all-nz
```

**Sources:** MetService weather warnings + NEMA civil defence alerts  
**Earthquakes:** Not included  
**Coverage:** All of New Zealand  
**Alerts per response:** Up to 100, ordered by severity (Extreme → Info) then recency

---

### 2. Official NZ — By Region

```
GET /cap/feeds/official/regions/{region}
```

**Sources:** MetService weather warnings + NEMA civil defence alerts  
**Earthquakes:** Not included  
**Coverage:** Single region only

| Slug | Region |
|------|--------|
| `northland` | Northland |
| `auckland` | Auckland |
| `waikato` | Waikato |
| `bay_of_plenty` | Bay of Plenty |
| `gisborne` | Gisborne / Tairāwhiti |
| `hawkes_bay` | Hawke's Bay |
| `taranaki` | Taranaki |
| `manawatu_whanganui` | Manawatū-Whanganui |
| `wellington` | Wellington |
| `nelson_tasman` | Nelson / Tasman |
| `marlborough` | Marlborough |
| `west_coast` | West Coast |
| `canterbury` | Canterbury |
| `otago` | Otago |
| `southland` | Southland |

Sub-region slugs are also accepted (e.g. `wellington_metro`, `christchurch`, `queenstown`). Sub-region alerts also carry their parent region tag, so subscribing to a parent region catches everything within it.

Returns **404** for an unrecognised region slug.

---

### 3. Official NZ + GeoNet Earthquakes — All New Zealand

```
GET /cap/feeds/official-plus-earthquakes/all-nz
```

**Sources:** MetService weather warnings + NEMA civil defence alerts + GeoNet earthquakes  
**Earthquakes:** GeoNet earthquakes M4.5 and above only  
**Coverage:** All of New Zealand

---

### 4. Official NZ + GeoNet Earthquakes — By Region

```
GET /cap/feeds/official-plus-earthquakes/regions/{region}
```

**Sources:** MetService weather warnings + NEMA civil defence alerts + GeoNet earthquakes M4.5+  
**Coverage:** Single region — same slug table as feed #2 above

---

### 5. Auckland Enhanced — With Earthquakes

```
GET /cap/feeds/auckland-enhanced/with-earthquakes
```

**Sources:** MetService weather warnings + NEMA civil defence alerts + Auckland Emergency Management alerts + GeoNet earthquakes M4.5+  
**Coverage:** Auckland region only  
**Note:** This is the most comprehensive feed available for Auckland. It is the only feed that includes AEM alerts.

---

### 6. Auckland Enhanced — Without Earthquakes

```
GET /cap/feeds/auckland-enhanced/no-earthquakes
```

**Sources:** MetService weather warnings + NEMA civil defence alerts + Auckland Emergency Management alerts  
**Coverage:** Auckland region only  
**Earthquakes:** Excluded

---

## Individual alert CAP documents

```
GET /cap/alerts/{id}
```

The `{id}` is the numeric NZ Alerts internal ID, found in the `href` attribute of the `<link rel="related" type="application/cap+xml">` element on each Atom feed entry.

**Behaviour:**
- If the source agency publishes their own CAP document → **HTTP 302 redirect** to the official URL
- For NEMA/MetService alerts where embedded CAP XML was stored → **serves the original XML verbatim**
- For GeoNet earthquakes and AEM alerts → **synthesises a valid CAP 1.2 document** on the fly from the normalised alert data
- If the alert has expired or been superseded → **HTTP 410 Gone**
- If the alert ID does not exist → **HTTP 404 Not Found**

### msgType behaviour in synthesised documents

Synthesised CAP documents (GeoNet earthquakes, AEM alerts) emit:
- `<msgType>Alert</msgType>` — for alerts where `updated_at` and `created_at` are within 5 minutes (i.e. newly ingested, not yet re-assessed)
- `<msgType>Update</msgType>` + `<references>` — for alerts where `updated_at` is more than 5 minutes after `created_at` (e.g. GeoNet re-assessing magnitude after initial ingest)

The `<references>` element points back to the original synthesised identifier (same tag URI, `created_at` timestamp).

---

## Alert inclusion rules

An alert appears in a feed if it meets **all** of the following:

1. `is_active = true` and `is_test = false`
2. Source is one of `geonet`, `metservice`, `nema`, `aem` (power outage sources are never included)
3. At least one of:
   - Has a `cap_url` pointing to an official CAP document
   - Has embedded CAP XML stored in `raw_payload._cap._xml`
   - Is an AEM alert (Auckland Enhanced feeds only)
   - Is a GeoNet earthquake M4.5+ (earthquake-inclusive feeds only)
4. Passes the feed's earthquake/region filter

---

## Atom entry structure

Each `<entry>` in the Atom feed contains:

| Element | Content |
|---------|---------|
| `<title>` | Alert headline |
| `<id>` | Stable tag URI identifier for this alert |
| `<category term="...">` | `Geo`, `Met`, `Safety`, `Infra`, or `Other` |
| `<summary>` | Plain-text description, truncated to 500 chars |
| `<updated>` | CAP `<sent>` time (or `updated_at` if not available) |
| `<published>` | Same as `<updated>` |
| `<author><name>` | Issuing agency name |
| `<link rel="related" type="application/cap+xml">` | URL to the CAP document for this alert |

---

## Beta status

These feeds are provided **free of charge** as part of ongoing beta testing. Access controls or pricing may be introduced in the future without notice.
