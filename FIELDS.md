# Field inventory — US Power Ocean Pro (HR51 / HR61)

Fields are addressed by the flattened protobuf path `1.1.<field>` on the app-MQTT stream.
See [`fieldmap.py`](fieldmap.py) for the authoritative map and units; this file summarizes
what's confirmed versus still being identified.

## Frames

| cmdFunc/cmdId | Device | Carries |
|---|---|---|
| `254 / 21` | inverter (HR51) | main telemetry burst: PV strings, PCS/inverter output, grid flows |
| `254 / 22` | inverter (HR51) | status frame: grid frequency/voltage/current, DC-bus voltage, fault register |
| `32 / 177` | inverter (HR51) | per-battery-pack scalars (one pack per frame) |
| `254 / 21` | panel (HR61) | 40-circuit array, circuit labels, grid/load flows, work mode |

## Confirmed fields (selected)

| Field(s) | Meaning | Notes |
|---|---|---|
| `1476–1483` | PV strings pv1–pv8 (W) | per-string production power |
| `53` | PCS total active power (W) | signed; negative = production/export |
| `517` | total solar (W) | inverter's own sum of the MPPT strings |
| `1463–1468` | PCS per-leg L1/L2 V / A / W | A/B → L1/L2 assignment provisional |
| `641` / `642` | grid frequency L1/L2 (Hz) | on `254/22`; ~60 Hz, wanders realistically |
| `643` / `644` | grid voltage L1/L2 (V) | ~120–123 V per leg |
| `645` / `646` | grid current L1/L2 (A) | tracks load |
| `1502` / `1503` | DC-bus voltage (V) | boosted ~5 V above battery terminal; `1510` ≈ 440 V ceiling |
| `1470` | EMS work mode (code) | matches EU `emsWorkMode` enum 0–9 (0 self-use … 2 backup … 9 timer) |
| `45` | battery pack voltage | 10 mV/count → V = value / 100 (~395–400 V) |
| `43` / `44` | battery pack current / power | signs confirmed (+ charge / − discharge) |
| `1512–1519` | fault/status register (8 slots) | see below |

## The fault/status register (`1512–1519`)

Eight parallel slots, baseline `0,0,0,0,0,2,0,2` (the steady `2`s are benign status/enum, not
fault flags). It matches the *shape* of the EU PowerOcean JSON, which carries per-subsystem code
fields (`bpErrCode`, `pcsAcErrCode`, `pcsDcErrCode`, `mppt1/2FaultCode`, `…WarningCode`). The
official US field name is `emsErrCode.errCode[]`. **No public dictionary maps the code numbers to
meanings** (US or EU) — a nonzero value would need EcoFlow to decode. Logged raw so any change is visible.

## How fields are confirmed — a worked example

DC-bus voltage was confirmed with a live load change (a ~4 kW load dropped, plus a battery
charge/discharge flip). At a frame where the battery block and status block coincided, the
battery terminal (`45`) read 395.5 V while `1502/1503/1511` read ~400–402 V — consistently ~5 V
above the battery, i.e. the boosted DC-link, with `1510` = 440 V as the fixed ceiling. Field `49`
tracked the battery terminal, not the bus, so it was ruled out as a second bus reading. See
[docs/methodology.md](docs/methodology.md).

## Candidate / unknown fields (live-varying, not yet identified)

Collected raw for identification (they populate the "unknown fields" view in the dashboards):

- **Inverter (HR51):** `22`, `50`, `518`, `1469`, `1472`, `1557`, `1560`, `1682`
- **Panel (HR61):** `518`, `962`–`967` (a live per-phase-looking block), `1227` (a large signed
  power), `1462`, `1485`, `1486`

If you have an HR51/HR61 system and can help identify these, please open an issue.

## Cross-product notes

- **Delta 3 / Delta Pro 3** share the `254/21` envelope field numbering only in the low range
  (up to ~field 458). The Ocean Pro's 600+/1400+ fields (grid, DC-bus, fault register) are
  Ocean-Pro-specific.
- **EU PowerOcean / Plus** use a different (`96`/JTS1) stream; field *numbers* do not transfer,
  though the field *names* are a useful vocabulary.
