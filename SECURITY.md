# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |
| < 1.0 | No |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

To report a security issue, open a private vulnerability report on GitHub:

1. Go to https://github.com/sshadmin147/HA_CAPWatcher_NZ/security/advisories/new
2. Describe the vulnerability, including steps to reproduce and potential impact
3. You will receive a response within 7 days

Alternatively, open a GitHub issue marked `[security]` if you are not able to use the private advisory flow. Do not include exploit details in a public issue.

## Scope

This integration polls public CAP feeds over HTTPS and creates read-only sensor entities in Home Assistant. It does not store credentials, transmit user data externally, or accept inbound connections.

Vulnerabilities of interest include:
- XML injection or XXE via malformed CAP feed responses
- Unsafe handling of attacker-controlled feed URLs in the custom feed option
- Credential or token exposure in logs or entity attributes
- Dependency vulnerabilities in `aiohttp` or `PyYAML`

Out of scope: vulnerabilities in the upstream CAP feed providers (MetService, NEMA, NZAlerts), or in Home Assistant itself.
