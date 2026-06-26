---
name: Bug report
about: Create a report to help us improve
title: "[BUG]"
labels: bug
assignees: ''

---

## Bug Description
<!-- A clear and concise description of what's going wrong. -->

## Feed Configuration
<!-- Which feeds are affected? Check all that apply. -->
- [ ] All New Zealand
- [ ] Auckland Enhanced (AEM + MetService + NEMA + GeoNet)
- [ ] Specific region (specify below)
- [ ] Custom feed URL (specify below)

**Region(s):** 
**Custom feed URL (if applicable):**

## Alert Source
<!-- Which alert provider does this relate to? -->
- [ ] MetService (weather warnings)
- [ ] NEMA (civil defence)
- [ ] GeoNet (earthquakes)
- [ ] AEM (Auckland Emergency Management)
- [ ] Not alert-specific / affects all feeds
- [ ] Unknown

## Steps to Reproduce
1. 
2. 
3. 

## Expected Behaviour
<!-- What should have happened? -->

## Actual Behaviour
<!-- What actually happened? -->

## Relevant Log Output
<!-- Filter HA logs by `custom_components.ha_capwatcher` and paste here. -->
```
paste logs here
```

## Environment
| Field | Value |
|---|---|
| HA-CAPWatcher version | |
| Home Assistant version | |
| Installation method | HACS / Manual |
| HA install type | OS / Container / Supervised / Core |
| Polling interval | |

## Diagnostic Checks
<!-- Tick any you've already tried. -->
- [ ] Checked HA logs for `[custom_components.ha_capwatcher]` errors
- [ ] Feed URL is reachable from HA host (tested in browser or `curl`)
- [ ] HA restarted after installation/update
- [ ] Issue persists after waiting at least one full polling cycle

## Additional Context
<!-- Anything else relevant — automation YAML, Lovelace card config, screenshots, etc. -->
