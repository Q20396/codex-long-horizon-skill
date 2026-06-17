# Monitoring Runbook

Do not include secrets, API keys, client names, legal evidence, family
information, medical information, financial account details, identity documents,
private correspondence, precise coordinates, or confidential source content.

This runbook should not enable live GPS access, continuous tracking, or
automatic location sharing. Use manual monitored locations by default.

## Purpose

-

## Scope

- Hazards monitored:
- Regions monitored:
- Out of scope:

## Monitored Locations

| Label | Method | Place name | Radius km | Precise location | Permission | Notes |
| --- | --- | --- | --- | --- | --- | --- |
|  | manual / user-approved-location / imported |  |  | false | none / one-time / customer-managed |  |

## Location Handling

- Default setup uses manually added locations:
- GPS/current location is optional and user-initiated:
- Current location, if used, is approximate and one-time:
- Precise coordinates are not stored unless explicitly requested:
- Continuous tracking is not enabled:
- Location is used only to configure alert rules:
- Manual alternative exists for each location flow:

## Sources And Notifiers

| Provider | Purpose | Location data sent | Customer configured | Notes |
| --- | --- | --- | --- | --- |
|  |  | None / Place / Region / Precise approved | Yes / No |  |

## Operations

- Setup steps:
- Test steps:
- Alert review cadence:
- Incident handoff:
- Rollback or disable steps:

## Stop Conditions

- Request requires continuous GPS tracking:
- Request sends precise location broadly by default:
- Sensitive location scope is unclear:
- Provider privacy behavior is unclear:
