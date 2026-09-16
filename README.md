# ecoflow-ocean-pro-us

**Reverse-engineered app-MQTT field map for the US EcoFlow Power Ocean Pro** — split-phase
(120/240 V), HR51 inverter + HR61 Ocean Smart Panel 40. An independent, substantially-extended
reverse-engineering of this product's telemetry, validated against a utility-meter-checked
collector.

This is **not** the EU 3-phase PowerOcean / PowerOcean Plus: different product, different
protocol (this unit streams `cmdFunc=254/21`; the EU units use the `96`/JTS1 stream), so the
EU field numbers do **not** transfer here.

> ⚠️ Empirical, **read-only**, work in progress. No official EcoFlow `.proto` exists for this
> product; every field was recovered from live captures and validated against a
> utility-meter-checked collector. Field meanings are best-effort and may be wrong. Use at your
> own risk.

## What this is (and isn't)

- **Is:** the field-number → meaning map ([`fieldmap.py`](fieldmap.py)), a zero-dependency
  schema-less protobuf decoder ([`protodump.py`](protodump.py)), the confirmed/unknown field
  inventory ([`FIELDS.md`](FIELDS.md)), and the [method](docs/methodology.md) used to confirm fields.
- **Isn't:** a plug-and-play integration. To run this in Home Assistant, use one of the
  integrations below.

## How it works

Telemetry is read from EcoFlow's **cloud** MQTT broker — it is entirely cloud-relayed:

```
Ocean Pro / Panel  ⇄  EcoFlow cloud MQTT broker  ⇄  phone app (and this decoder)
                          (mqtt.ecoflow.com)
```

You authenticate to that same cloud broker with app credentials and subscribe to the device's
`/app/device/property/<sn>` topics — a second listener on the cloud stream. Frames are protobuf;
fields are addressed by the flattened path `1.1.<field>`, matched on the **exact** path (small
field numbers recur inside nested submessages).

- `cmdFunc=254 cmdId=21` — main telemetry burst (PV strings, PCS/inverter output, grid flows)
- `cmdFunc=254 cmdId=22` — status frame (grid frequency/voltage/current, DC-bus voltage, fault register)
- `cmdFunc=32 cmdId=177` — per-battery-pack scalars (one pack per frame)

**Read-only.** This project only observes the stream (it publishes `get` polls to trigger
telemetry — nothing else). The protocol is bidirectional (the app issues `set` commands, which
round-trip app → cloud → device), but control/write is intentionally out of scope: writing to a
live home battery/panel is risky and unsupported here.

## The system this was mapped from

- **Inverter:** EcoFlow Power Ocean Pro (HR51 series), split-phase 120/240 V
- **Panel:** Ocean Smart Panel 40 (HR61 series), 40 circuits, on a 200 A / 240 V split-phase
  service (upgraded from 100 A when the panel was installed)
- **Battery:** 4× PowerOcean battery packs (~400 V DC class)
- **Solar:** 45 × Canadian Solar CS3W-450MS (450 W) = **20.25 kW**, wired as 8 PV strings
  across 3 roof planes (east / west-mid / west-far)

## What's decoded

See [`fieldmap.py`](fieldmap.py) for the full map and [`FIELDS.md`](FIELDS.md) for confirmed vs.
still-unidentified fields. Highlights:

- **PV strings** pv1–pv8, per-string production power
- **Inverter / PCS** total + per-leg (L1/L2) voltage, current, active power
- **Grid** frequency, per-leg voltage/current
- **DC-bus** (DC-link) voltage
- **Battery** per-pack voltage, current, SOC; bank rollup; work mode
- **Fault/status register** (8 slots) — a bank of per-subsystem codes; **no public dictionary
  maps the code numbers to meanings** (US or EU), so a nonzero value needs EcoFlow to decode

## Try the decoder

```bash
python3 protodump.py your-capture.jsonl --sn HR51 --summary
```

Zero dependencies (Python standard library only). Supply your own capture — a JSONL of records
like `{"topic": ".../<sn>", "kind": "hex", "payload": "<hex protobuf>"}`, one per MQTT message.
`--summary` prints every field path with its mapped meaning and sample values; drop it to see
decoded frames.

## Relationship to other EcoFlow products

Specific to the **Power Ocean Pro (HR51) + Ocean Smart Panel 40 (HR61)**. It is **not**:

- **Delta 3 / Delta Pro 3** — portable power stations. They share the `254/21` envelope field
  numbering in the low range (the HA integrations subclass Delta Pro 3 for that part), but the
  Ocean Pro's PV-string, grid, DC-bus, and fault fields (600+/1400+) are unique to it.
- **Smart Home Panel 2 / 3** — the Ocean Smart Panel 40 reuses the SHP3 circuit layout widened
  from 32 to 40 circuits, but it is a separate device.
- **EU PowerOcean / PowerOcean Plus** — a different (3-phase) product on the `96`/JTS1 protocol;
  field numbers do not transfer.

## Using this in Home Assistant

Two integrations support this hardware:

- **[tolwi/hassio-ecoflow-cloud](https://github.com/tolwi/hassio-ecoflow-cloud)** — the
  actively-maintained, multi-device integration. I contributed the Ocean Pro profile + fixes:
  **#892** (merged, v1.7.0) read-only Ocean Pro support; **#894** (merged, v1.7.1) reject
  implausible battery-power spikes; **#914** (open) derive battery power from PV + PCS. *Recommended.*
- **[redawg/ecoflow-ocean-ha](https://github.com/redawg/ecoflow-ocean-ha)** — a standalone,
  dedicated US Power Ocean integration; the independent effort this field map was cross-checked against.

## Roadmap & collaboration

Beyond the field map, I've built a web dashboard and Home Assistant dashboards on top of this
data with analytics I haven't seen elsewhere in the EcoFlow community. I plan to publish
sanitized versions here as they mature:

- **Forecast-driven off-grid projection** — projects battery SoC forward hour-by-hour over a real
  7-day weather forecast for an outage starting *now*, combining forecast solar (GHI) with
  temperature-driven HVAC load and an essentials base draw, to estimate **how many days you could
  run off-grid** under the actual coming weather.
- **Backup runtime planner** — live "hours/days of runtime remaining" from current load and SoC.
- **Billing / cost card** — bill-to-date with time-of-use peak vs off-peak rates; import vs production.
- **Battery SoC strategy** — evaluates the charge strategy (nightly grid-charge timing,
  top-of-charge hold, self-sufficiency) against what actually happened.
- **Per-string PV health instrumentation** — tracks each string's daily energy against its
  nameplate DC rating and a weather-normalized expectation, so you can tell **degradation vs.
  soiling (needs cleaning) vs. shading vs. a genuine fault** apart instead of guessing.

**Other US Ocean Pro (HR51/HR61) owners:** I'd love to compare notes — open a
[GitHub Issue](../../issues) or [Discussion](../../discussions). Captures from a second unit would
help validate the still-unidentified fields. I'm also happy to contribute findings back into
either Home Assistant integration (tolwi or redawg) if the maintainers are interested.

## Credits / prior art

- **[redawg/ecoflow-ocean-ha](https://github.com/redawg/ecoflow-ocean-ha)** — an independent US
  Power Ocean reverse-engineering effort, used here to **cross-check and validate**. This project
  builds well beyond it: additional decoded blocks the earlier map didn't have (grid frequency,
  grid voltage/current per leg, DC-bus voltage, the 8-slot fault register), field-level
  corrections, per-string PV-health instrumentation, and validation against a utility-meter-checked
  collector — plus forecast-driven analytics and dashboards.
- **[tolwi/hassio-ecoflow-cloud](https://github.com/tolwi/hassio-ecoflow-cloud)** — the Home
  Assistant integration this work is contributed into.
- **[foxthefox/ioBroker.ecoflow-mqtt](https://github.com/foxthefox/ioBroker.ecoflow-mqtt)** — the
  EU PowerOcean field vocabulary (names, not numbers).
- Feberdin/ecoflow-powerocean-ha, niltrip/powerocean — additional EU PowerOcean references.

## Disclaimer

Independent, unofficial, read-only. Not affiliated with or endorsed by EcoFlow. Field meanings
are best-effort and may be wrong; verify before relying on any value.
