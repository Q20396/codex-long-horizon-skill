# Disaster Alert Rule

Do not include secrets, API keys, client names, legal evidence, family
information, medical information, financial account details, identity documents,
private correspondence, precise coordinates, or confidential source content.

Location is used only to configure alert rules. Default setup should use
manually added monitored locations. GPS/current location is optional,
user-initiated, one-time, and approximate unless the customer explicitly
requests precise monitoring.

## Rule Summary

- Rule label:
- Hazard type:
- Severity threshold:
- Alert priority:
- Enabled: true / false

## Monitoring Location

```yaml
label:
method: manual # manual / user-approved-location / imported
place_name:
radius_km:
precise_location: false
location_permission: none # none / one-time / customer-managed
notes:
```

## Location Consent

- GPS required: No
- Manual alternative available: Yes
- Current location used: No / One-time approved / Not applicable
- Precise coordinates stored: No / Explicitly approved
- Continuous tracking enabled: No
- External provider receives location: No / Explicitly configured

## Sources

| Source | Purpose | Location shared | Notes |
| --- | --- | --- | --- |
|  |  | None / Place / Region / Precise approved |  |

## Notification Plan

- Channels:
- Recipients or roles:
- Quiet hours:
- Escalation:

## Review

- Privacy review:
- Test method:
- Last reviewed:
