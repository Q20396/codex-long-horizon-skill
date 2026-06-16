# Disaster Monitoring Enablement

Use this guide when helping a customer design disaster, earthquake, flood,
fire, storm, tsunami, outage, or emergency alert monitoring.

This protocol is for configuring alert rules and runbooks. It does not enable
real GPS access, background tracking, live emergency response, or direct
integration with disaster APIs by itself.

## Privacy-First Location Rules

- Do not require GPS or device location permission by default.
- Default setup should ask the customer to manually add monitored locations.
- GPS or current location must be optional and user-initiated only.
- If current location is used, prefer approximate place or region plus a radius,
  not precise coordinates.
- Do not store precise coordinates unless the customer explicitly requests
  precise monitoring.
- Do not continuously track location.
- Do not send location to external providers unless the customer explicitly
  configures a source or notifier that requires it.
- Explain that location is used only to configure alert rules.
- Provide a manual alternative for every GPS-based flow.

If the customer asks for continuous tracking or broad location sharing, stop and
offer a manual, approximate, customer-managed alternative.

## Default Setup Flow

Start with manual setup:

1. Ask the customer which places they want to monitor.
2. Ask for a label, such as `Home`, `Melbourne office`, or `Tokyo family`.
3. Ask for a place name, region, or area.
4. Ask for an approximate radius in kilometers.
5. Ask which hazards matter.
6. Ask which approved public sources or customer-managed notifiers should be
   used.
7. Confirm that no GPS permission is required for the default setup.

## Optional Current Location Flow

Use current location only when the customer asks for it or approves it.

Before using current location, explain:

- Why location is needed.
- That it will be used only to configure alert rules.
- That approximate place/region and radius are preferred.
- That precise coordinates are not stored unless explicitly requested.
- That there is no continuous tracking.
- Which source, if any, will receive location data.

Manual alternative:

```text
You can also type the place or region manually, such as "Melbourne CBD within
25 km", and I will configure the rule without using GPS.
```

## Monitoring Location Fields

Use this shape for monitored locations:

```yaml
label:
method: manual # manual / user-approved-location / imported
place_name:
radius_km:
precise_location: false
location_permission: none # none / one-time / customer-managed
notes:
```

Field guidance:

- `label`: Customer-friendly name for the monitored area.
- `method`: How the location was provided.
- `place_name`: Human-readable place, region, suburb, city, or area.
- `radius_km`: Approximate monitoring radius.
- `precise_location`: `true` only when the customer explicitly requests precise
  monitoring.
- `location_permission`: `none` for manual entries, `one-time` for an approved
  current-location lookup, or `customer-managed` when the customer configures
  location in another system.
- `notes`: Non-sensitive configuration notes only.

## External Providers

Do not send location to external providers by default.

If an alert source, weather service, earthquake API, map provider, SMS provider,
email system, webhook, or notifier requires location data:

1. Name the provider.
2. Explain what data would be sent.
3. Prefer place name or coarse region over precise coordinates.
4. Ask the customer to approve that provider-specific configuration.
5. Record only the minimum non-sensitive configuration needed.

## Stop Conditions

Pause and ask before continuing if:

- The user asks for continuous GPS tracking.
- The user asks to send precise location to all providers by default.
- The flow would store precise coordinates without explicit approval.
- The requested source or notifier would expose private location data.
- The task involves family, client, legal, medical, or safety-sensitive
  locations and the scope is unclear.
