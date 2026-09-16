# Methodology

How fields in this map were recovered and confirmed, without an official `.proto`.

## 1. Capture the stream

Subscribe to EcoFlow's cloud MQTT broker with app credentials and record every frame on the
device's `/app/device/property/<sn>` topics as `{topic, kind, payload}` JSONL (hex payloads).

## 2. Decode structurally

Protobuf's wire format is self-describing enough to recover field numbers, wire types, and
values without a schema. [`protodump.py`](../protodump.py) parses each frame into
`field-path → value`, recursing into submessages. `--summary` aggregates the distinct values
seen per path across a capture, which is what makes a field's behavior visible.

## 3. Identify by behavior, not by guessing

A field's meaning is inferred from **how its value moves**:

- **Correlate with a known change.** Toggle a large load and watch which fields move with it
  (grid current, PCS power), which flip sign (battery power on a charge/discharge transition),
  and which stay stiff (a regulated DC bus). This is how DC-bus voltage was told apart from the
  battery terminal — at a coincident frame the bus read ~5 V above the battery and held steady.
- **Sanity-check magnitude and units.** ~60 Hz that wanders ±0.02 is grid frequency; a fixed
  59/60/61 triplet is a protection setpoint. ~400 V is the battery/DC side; ~120 V is a grid leg.
- **Validate against ground truth.** Values are checked against a utility-meter-validated
  collector and the owner's known configuration (backup reserve, charge ceiling, mode schedule).

## 4. Guard against field-number reuse

Small field numbers recur inside unrelated nested submessages. Every field is matched on the
**exact** path `1.1.<field>` (top-level), and physical fields are range-guarded (e.g. a PV value
outside a sane wattage range, or a "grid voltage" outside 100–300 V, is reuse leaking through and
is rejected).

## 5. Cross-check against prior art

Field numbers are compared against an independent US Power Ocean reverse-engineering effort
(redawg/ecoflow-ocean-ha) to confirm overlap, and against the EU PowerOcean field *names*
(foxthefox) as a vocabulary for what to look for — though the EU field *numbers* do not transfer.

## Caveats

Everything here is empirical. The L1/L2 (phase A/B) assignment and some power-sign conventions
are provisional until settled against a controlled change. Fault-code *numbers* have no public
meaning table anywhere. Treat any value as best-effort until independently confirmed.
