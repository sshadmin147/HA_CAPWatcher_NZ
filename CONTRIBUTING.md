# Contributing to HA-CAPWatcher NZ

Thank you for taking the time to contribute. This document covers everything you need to get set up, write good code, and get your changes merged.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting Code](#submitting-code)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Standards](#code-standards)
- [Commit Messages](#commit-messages)
- [Branch Naming](#branch-naming)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Key Concepts](#key-concepts)

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating you agree to uphold it. Unacceptable behaviour can be reported by opening a GitHub issue marked `[conduct]` or contacting the maintainer directly.

In short: be respectful, be constructive, assume good intent.

---

## How to Contribute

### Reporting Bugs

Before opening an issue, check that it hasn't already been reported.

When filing a bug, include:

- **HA version** (Settings → System → About)
- **Integration version** (Settings → Devices & Services → HA-CAPWatcher → Info)
- **The full log error** from Settings → System → Logs, filtered to `ha_capwatcher`
- **What you expected** to happen
- **What actually happened**
- **Steps to reproduce** (which feed, which polling interval, etc.)

Open issues here: https://github.com/sshadmin147/HA_CAPWatcher_NZ/issues

### Suggesting Features

Open an issue with the `enhancement` label. Describe:

- What problem you're trying to solve (not just the solution)
- Who else would benefit from it
- Whether it belongs in Stage 1 (the integration layer) or Stage 2 (the Lovelace card — separate repo)

Feature suggestions without a clear use case are unlikely to be actioned.

### Submitting Code

- For small fixes (typos, single-line corrections), a PR with a clear description is enough.
- For anything larger, open an issue first and discuss the approach before writing code. This avoids wasted effort.
- All PRs require tests. A fix without a test for the thing that was broken will be sent back.

---

## Development Setup

### Prerequisites

- Python 3.11 or later
- Git

No Home Assistant installation is required. The test suite stubs all HA modules.

### Clone and install

```bash
git clone https://github.com/sshadmin147/HA_CAPWatcher_NZ.git
cd HA_CAPWatcher_NZ
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install pytest pytest-asyncio aiohttp PyYAML
```

### Verify setup

```bash
python -m pytest tests/ -v
```

You should see `148 passed, 29 skipped` (the skipped tests are manual live-HA QA steps and are expected).

---

## Running Tests

### Full suite

```bash
python -m pytest tests/ -v
```

### Single file

```bash
python -m pytest tests/test_coordinator.py -v
```

### Single test

```bash
python -m pytest tests/test_parser.py::TestParseCAPDocument::test_cap12_moderate_maps_to_warning -v
```

### Skip the live QA file (faster)

```bash
python -m pytest tests/ -v --ignore=tests/test_step10_live_ha_qa.py
```

### Test files and what they cover

| File | Covers |
|---|---|
| `test_parser.py` | Atom feed parsing, CAP document parsing, severity mapping |
| `test_coordinator.py` | Rate limit queue, polling lifecycle, error handling, cache |
| `test_sensor.py` | Alert sensor properties, entity lifecycle, aggregate helpers |
| `test_config_flow.py` | Config flow and options flow validation |
| `test_feeds_loader.py` | Default feed loading, validation, merging |
| `test_multi_feed.py` | Feed isolation, shared rate queue, multi-coordinator setup |
| `test_reload.py` | Unload, session cleanup, cache reset on reload |
| `test_step10_live_ha_qa.py` | Manual QA checklist for live HA (all skipped in CI) |

### Adding tests

- Every bug fix must include a test that fails before the fix and passes after.
- Every new function must have tests covering at least: the happy path, one edge case, and one failure case.
- Tests live in `tests/`, named `test_<module>.py`.
- Use `@pytest.mark.asyncio` for async tests. Use `MagicMock` / `AsyncMock` from `unittest.mock` — no extra mocking libraries.
- Do not import `homeassistant` directly in tests. The stubs in `tests/conftest.py` cover everything needed; add new stubs there if you add imports in component code.

---

## Code Standards

### Python version

Write for Python 3.11+. Use `from __future__ import annotations` at the top of every file.

### Style

- **Formatting:** PEP 8. Keep lines under 100 characters.
- **Type hints:** Required on all function signatures (arguments and return types).
- **Comments:** Write no comments by default. Add one only when the *why* is non-obvious — a hidden constraint, a workaround for a specific bug, something that would surprise a reader. If removing the comment wouldn't confuse anyone, don't write it.
- **Docstrings:** Short single-line docstrings on public functions only. No multi-paragraph blocks.
- **No dead code:** Don't leave commented-out code, unused imports, or placeholder `pass` blocks.

### Error handling

- Only handle errors at system boundaries (HTTP responses, file I/O, external data). Don't wrap internal logic in try/except to hide bugs.
- Log errors with `_LOGGER.warning(...)` or `_LOGGER.error(...)` — never `print()`.
- Use `UpdateFailed` to signal a coordinator poll failure. HA handles the retry/backoff from there.
- If a CAP alert is missing a mandatory field, skip that alert and log the reason. Don't guess, infer, or silently drop.

### Async rules

- All network I/O goes through `aiohttp` and must be awaited.
- All file I/O (e.g. loading `default_feeds.yaml`) must use `hass.async_add_executor_job(...)` to avoid blocking the event loop.
- Never call `time.sleep()` in async code. Use `asyncio.sleep()` if a delay is genuinely needed (it usually isn't).

### CAP and NZ-CAP standards

- Severity values in entities are always lowercase NZ-CAP strings: `extreme`, `severe`, `warning`, `watch`, `info`.
- Raw CAP 1.2 values (`Moderate`, `Minor`, `Unknown`) are mapped in `severity.py` — do not map them anywhere else.
- Severity colors are defined once in `const.py`. Do not hardcode hex values anywhere else in the codebase.
- If the NZ-CAP standard says a field is mandatory, it must be present. Do not work around missing mandatory fields.

### Feed names

Feed `name` values must match `^[a-z][a-z0-9_]*$` — lowercase, underscores only, no hyphens. This keeps HA entity IDs clean.

---

## Commit Messages

Use the following format:

```
<type>: <short summary in present tense, under 72 chars>

<optional body — explain WHY, not what. Wrap at 72 chars.>
```

**Types:**

| Type | When to use |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fix |
| `test` | Adding or updating tests only |
| `chore` | Version bumps, dependency updates, config changes |
| `docs` | Documentation only |
| `refactor` | Code restructure with no behaviour change |

**Examples:**

```
fix: map CAP 1.2 Moderate severity to NZ-CAP warning

MetService publishes Moderate/Minor/Unknown rather than NZ-specific
values. These were being silently skipped as unknown severity.
```

```
feat: add shared rate limit queue across coordinators
```

```
test: add expiry isolation tests for multi-feed setup
```

Do not use `update`, `change`, `improve`, or `misc` as the type. If you can't pick one of the six types above, the commit is probably doing too much — split it.

---

## Branch Naming

```
fix/<short-description>         fix/moderate-severity-mapping
feat/<short-description>        feat/custom-feed-validation
test/<short-description>        test/coordinator-backoff-coverage
docs/<short-description>        docs/stage2-design
chore/<short-description>       chore/bump-aiohttp-requirement
```

Branch off `main`. Do not commit directly to `main`.

---

## Pull Request Process

1. **Branch** from the latest `main`.
2. **Write tests** before or alongside your code — not after.
3. **Run the full suite** locally and confirm it passes: `python -m pytest tests/ -v`.
4. **Open the PR** against `main` with a clear title (same format as a commit message) and a description covering:
   - What the PR does
   - Why it's needed (link to issue if applicable)
   - How to test it manually if relevant
5. **PR checklist** — your PR will not be merged until:
   - [ ] All existing tests pass
   - [ ] New tests cover the change
   - [ ] No new blocking calls to file/network I/O inside async functions
   - [ ] Type hints present on all new functions
   - [ ] `manifest.json` version bumped if the change affects runtime behaviour
6. **Review** — at least one approval is required from a maintainer. Address feedback by pushing new commits to the same branch, not by force-pushing.
7. **Merge** — squash merge preferred for single-concern changes; merge commit for larger features that benefit from preserved history.

---

## Project Structure

```
HA_CAPWatcher_NZ/
├── custom_components/
│   └── ha_capwatcher/
│       ├── __init__.py          # Entry setup and teardown
│       ├── manifest.json        # HA integration manifest
│       ├── const.py             # All constants (severities, colors, config keys)
│       ├── config_flow.py       # UI config and options flows
│       ├── coordinator.py       # CAPFeedCoordinator, RateLimitQueue, FeedData
│       ├── parser.py            # Atom + CAP XML parsers, ParsedAlert dataclass
│       ├── sensor.py            # HA sensor entities and aggregate helpers
│       ├── severity.py          # Severity validation, normalization, color lookup
│       ├── feeds_loader.py      # YAML loader, feed validation, merge logic
│       └── default_feeds.yaml   # Bundled NZAlerts feed definitions
├── tests/
│   ├── conftest.py              # HA module stubs (required — no HA install needed)
│   ├── test_coordinator.py
│   ├── test_parser.py
│   ├── test_sensor.py
│   ├── test_config_flow.py
│   ├── test_feeds_loader.py
│   ├── test_multi_feed.py
│   ├── test_reload.py
│   └── test_step10_live_ha_qa.py
├── docs/
│   ├── DESIGN_STAGE1.md
│   ├── DESIGN_STAGE2.md
│   └── TEST_PLAN_STAGE1.md
├── hacs.json
├── LICENSE
├── README.md
└── CONTRIBUTING.md              # This file
```

### Where things live

- **New constants** → `const.py`
- **New severity mappings** → `severity.py` (`_CAP12_TO_NZCAP` dict)
- **New feed definitions** → `default_feeds.yaml`
- **Feed validation rules** → `feeds_loader.py` (`validate_feed`)
- **Parser changes** → `parser.py` (`parse_atom_feed`, `parse_cap_document`)
- **New entity types** → `sensor.py`
- **Polling/error handling** → `coordinator.py`

---

## Key Concepts

A few things that are easy to get wrong the first time:

**Two-phase fetch.** Each poll does two HTTP requests per new alert: (1) the Atom feed to discover new alert IDs, then (2) individual CAP document fetches for any alert not already in the cache. The cache avoids re-fetching CAP docs for alerts that are still active.

**Alert expiry by absence.** Alerts are removed when they are no longer present in the Atom feed on the next poll. The `expires` timestamp in the CAP data is stored as an attribute but is not used for eviction logic.

**Late-binding closures.** The `_setup_feed_entities` function in `sensor.py` uses default-argument capture (`_coord=coordinator, _tracked=tracked`) inside loops. This is intentional — Python closures capture variables by reference, so without the default argument the loop variable would have moved on by the time the callback fires.

**Aggregate entities use `Entity`, not `CoordinatorEntity`.** The three helper sensors (`CAPAlertCountSensor`, `CAPHighestSeveritySensor`, `CAPLatestHeadlineSensor`) subscribe to multiple coordinators manually in `async_added_to_hass`. They cannot inherit from `CoordinatorEntity` because that class is designed for a single coordinator relationship.

**HA module stubs in tests.** `tests/conftest.py` registers stub modules in `sys.modules` before any component code is imported. If you add a new `from homeassistant.x import Y` in component code, you must add a corresponding stub in `conftest.py` or tests will fail with `ModuleNotFoundError`.

---

## License

By contributing to this project you agree that your contributions will be licensed under the same [MIT License](LICENSE) that covers the project.
