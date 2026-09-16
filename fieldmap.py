"""Field-number → meaning map for the Ocean Pro app-MQTT protobuf.

The US OCEAN Pro (product type 88, ``HR51…``) publishes live telemetry primarily
under ``cmdFunc=254``, not the EU PowerOcean ``cmdFunc=96`` ENERGY_STREAM envelope.
There is no published ``.proto`` for it; this map was built empirically from live
captures and validated against a utility-meter-checked collector. Field numbers were
cross-checked against an independent US Power Ocean reverse-engineering effort
(https://github.com/redawg/ecoflow-ocean-ha) to confirm the overlap; the map here goes
substantially further — additional decoded blocks (grid frequency/voltage/current,
DC-bus voltage, the fault register), field-level corrections, and per-string PV work.

Everything here is empirical and partly unconfirmed — in particular the L1/L2 (phase
A/B) assignment and the battery/total-power **sign** convention. Treat power signs as
provisional until settled against a known load change.

Paths use the same dotted form ``protodump.flatten_paths`` emits (e.g. ``1.1.515``);
the leaf integer is the protobuf field number matched below.
"""

from __future__ import annotations

# --- Inverter telemetry, header.pdata leaf fields (cmdFunc=254) --------------
# field number -> (name, unit, note)
INVERTER_FIELDS: dict[int, tuple[str, str, str]] = {
    21: ("pcs_total_power_abs", "W", "total active power magnitude twin (cmdId 25)"),
    53: (
        "pcs_total_power",
        "W",
        "PCS total active power (= 1467+1468), signed; negative = production/export",
    ),
    262: (
        "system_soc_pct",
        "%",
        "system SOC — the reliable one: tracks bp_soc (100/100 and 91.0/91.64 in two "
        "captures a day apart). NOT field 1448, despite that field's name upstream.",
    ),
    515: ("grid_power", "W", "grid exchange; negative = export, positive = import"),
    516: ("grid_residual", "W", "= 517 + 515, not battery"),
    517: ("solar_mirror", "W", "tracks sum of MPPT string power"),
    1005: ("pack1_soc", "%", "per-pack SOC (nested .5 = %)"),
    1006: ("pack2_soc", "%", "per-pack SOC (nested .5 = %)"),
    1007: ("pack3_soc", "%", "per-pack SOC (nested .5 = %)"),
    1008: ("pack4_soc", "%", "per-pack SOC (nested .5 = %)"),
    1448: (
        "unknown_1448",
        "code",
        "NOT system SOC — mislabelled upstream. Alternates between exactly 0 and 30 "
        "within a single cmdId=21 burst (0,30,0,30…), which no charge level does, and "
        "disagreed with bp_soc/262 in both captures (8.57 vs 91, 15 vs 100 — the "
        "non-integer values are just the mean of a 0/30 mix). Discrete flag or code; "
        "meaning unknown, so not logged. Neighbours 1447/1454–1458 are all 1, 1449 is 0.",
    ),
    1463: ("pcsA_voltage", "V", "PCS phase A voltage — A/B assignment provisional"),
    1464: ("pcsA_current", "A", "PCS phase A current"),
    1465: ("pcsB_voltage", "V", "PCS phase B voltage"),
    1466: ("pcsB_current", "A", "PCS phase B current"),
    1467: ("pcsA_power", "W", "PCS phase A active power"),
    1468: ("pcsB_power", "W", "PCS phase B active power"),
    1470: ("work_mode", "code", "EMS operating mode — see WORK_MODE_CODES"),
    # 8 individual MPPT/PV inputs (pv1–pv8). redawg's app view groups 1476–1479 as
    # "strings 1–4" and 1480–1483 as a combined "string 5"; kept per-input here.
    1476: ("pv1_power", "W", "PV/MPPT input 1 power"),
    1477: ("pv2_power", "W", "PV/MPPT input 2 power"),
    1478: ("pv3_power", "W", "PV/MPPT input 3 power"),
    1479: ("pv4_power", "W", "PV/MPPT input 4 power"),
    1480: ("pv5_power", "W", "PV/MPPT input 5 power"),
    1481: ("pv6_power", "W", "PV/MPPT input 6 power"),
    1482: ("pv7_power", "W", "PV/MPPT input 7 power"),
    1483: ("pv8_power", "W", "PV/MPPT input 8 power"),
    1553: ("inverter_temp1", "C", "inverter temperature"),
    1554: ("inverter_temp2", "C", "inverter temperature"),
    1555: ("inverter_temp3", "C", "inverter temperature"),
    1556: ("inverter_temp4", "C", "inverter temperature"),
    # Grid-side metering block, per split-phase leg (L1/L2). Confirmed 2026-09-15 from a
    # live capture: 645/646 currents fell (29/47 -> 10/19 A) when a ~4 kW load dropped,
    # and 641/642 wander 59.97-60.02 Hz like real grid frequency (not the fixed 59/60/61
    # protection setpoints at 94/68/95). Rides cmdFunc=254 cmdId=22, not the cmdId=21
    # telemetry burst. Distinct from the PCS/inverter-output block at 1463-1468.
    641: ("grid_freq_l1", "Hz", "grid frequency, L1 leg — L2 twin = 642"),
    642: ("grid_freq_l2", "Hz", "grid frequency, L2 leg"),
    643: ("grid_voltage_l1", "V", "grid voltage, L1 leg"),
    644: ("grid_voltage_l2", "V", "grid voltage, L2 leg"),
    645: ("grid_current_l1", "A", "grid current, L1 leg — tracks load"),
    646: ("grid_current_l2", "A", "grid current, L2 leg — tracks load"),
    # DC-bus (DC-link) voltage. Confirmed 2026-09-15: at a coincident frame the battery
    # terminal (field 45) read 395.5 V while these read ~400-402 V, i.e. the link boosted
    # ~5 V above the battery, with 1510 = 440 the fixed ceiling/setpoint. Distinct from the
    # battery-terminal twin (field 49). Rides cmdFunc=254 cmdId=22. NOT logged by default
    # (see SYS_FIELDS) — diagnostic for the grid-blip/islanding case (ticket 2762).
    1502: ("dc_bus_voltage", "V", "DC-link bus voltage — boosted ~5 V above battery"),
    1503: ("dc_bus_voltage2", "V", "DC-link bus voltage, second reading"),
    1510: ("dc_bus_ceiling", "V", "DC-bus voltage ceiling/setpoint (constant ~440)"),
    1511: ("dc_bus_voltage3", "V", "DC-link bus voltage, third reading"),
    # Fault/status register, 8 slots. Confirmed 2026-09-15 as a stable block reading
    # 0,0,0,0,0,2,0,2 across a load change (the two 2's are steady = benign status/enum,
    # not fault flags). Slot meanings unknown — no fault occurred to move them. Logged as
    # codes (last value, never averaged) so a future nonzero change is trustworthy. Rides
    # cmdFunc=254 cmdId=22 (also echoed on the 240/1 get_reply).
    #
    # Likely a BANK of per-subsystem err/warn codes, not one fault word — the EU PowerOcean
    # JSON (foxthefox) carries exactly this shape as parallel fields: bpErrCode, pcsAcErrCode,
    # pcsDcErrCode, pcsAcWarningCode, mppt1/2FaultCode, mppt1/2WarningCode. The official US
    # field is emsErrCode.errCode[] (an int array). No public dictionary maps the code NUMBERS
    # to meanings anywhere (US or EU) — a live nonzero would need EcoFlow to decode.
    1512: ("fault_1512", "code", "fault/status register slot 0"),
    1513: ("fault_1513", "code", "fault/status register slot 1"),
    1514: ("fault_1514", "code", "fault/status register slot 2"),
    1515: ("fault_1515", "code", "fault/status register slot 3"),
    1516: ("fault_1516", "code", "fault/status register slot 4"),
    1517: ("fault_1517", "code", "fault/status register slot 5"),
    1518: ("fault_1518", "code", "fault/status register slot 6"),
    1519: ("fault_1519", "code", "fault/status register slot 7"),
}

# Fault/status register field numbers — logged as codes (last-value), never averaged.
FAULT_FIELDS: tuple[int, ...] = tuple(range(1512, 1520))

# --- Battery pack snapshot, pdata under src=3, cmdFunc=32, cmdId=177 ---------
# NOT the classic JTS1 bpSta numbering.
BATTERY_PACK_CMD = (32, 177)  # (cmdFunc, cmdId)
BATTERY_PACK_FIELDS: dict[int, tuple[str, str, str]] = {
    3: ("bp_sn", "", "serial number"),
    5: ("bp_slot", "", "pack slot index"),
    10: ("bp_soc_display", "%", "rounded SOC twin of field 11"),
    11: ("bp_soc", "%", "real per-pack charge level (matches app)"),
    12: ("bp_flag", "", "flag / power twin"),
    20: ("bp_soh", "%", "state of health, bank-shared ~99.9% — NOT charge level"),
    22: ("bp_env_temp", "C", "environment temperature"),
    29: ("bp_remain_wh", "Wh", "remaining energy"),
    33: ("bp_cell_temp_max", "C", "max cell temperature"),
    34: ("bp_cell_temp_min", "C", "min cell temperature"),
    43: ("bp_current", "dA", "current in deci-amps"),
    44: ("bp_power", "W", "pack power; positive = charging, negative = discharging (confirmed 2026-08-14 vs SoC direction, n=760)"),
    # NOT millivolts, despite the name kept here for continuity with logged rows: the
    # official EF-BP-10 datasheet rates the pack at 400 V DC over a 380-550 V range, and
    # the logged values span 38932-42680, i.e. 389.3-426.8 V at 10 mV per count. Read as
    # millivolts they would be 39-43 V, a tenth of rated and outside the operating range
    # entirely. Divide by 100 for volts.
    45: ("bp_voltage_mv", "10mV", "pack voltage, 10 mV per count -> volts = value / 100"),
}

# PV/MPPT input power fields, pv1..pv8 -> field number (inverter, HR51…).
PV_STRING_FIELDS: dict[int, int] = {n: 1475 + n for n in range(1, 9)}

# System-level scalars the logger persists alongside pv/circuit rows, as
# ``source='sys'``. Needed to tell curtailment from weather: with no PTO there is no
# export, so once the battery is full the inverter throttles PV to house load and output
# stops measuring sunlight. A full battery + zero grid export is the signature.
# These all arrive at path ``1.1.<field>`` on cmdFunc=254 frames.
SYS_FIELDS: dict[int, str] = {
    262: "system_soc_pct",  # %  — battery full is the precondition for curtailment
    515: "grid_power",  # W  — negative = export; positive = import
    517: "solar_total",  # W  — inverter's own sum of the MPPT strings
    53: "pcs_total_power",  # W  — inverter AC output (= 1467 + 1468)
    1470: "work_mode",  # code — see WORK_MODE_CODES
    # Per-phase A/B legs. pcs_total (53) is only their sum, so the individual legs were
    # invisible until now; logged so the HA profile has real L1/L2 history to validate
    # against. A/B -> L1/L2 *naming* still unconfirmed (needs the panel leg map or a
    # single-leg load test); the numbers are correct, only the label is provisional.
    1463: "pcsA_voltage",  # V
    1464: "pcsA_current",  # A
    1465: "pcsB_voltage",  # V
    1466: "pcsB_current",  # A
    1467: "pcsA_power",  # W  — sign follows pcs_total (negative = production/export)
    1468: "pcsB_power",  # W
    # Grid frequency — one value for the grid (L1 == L2), logged from the L1 leg. The
    # grid-blip case (ticket 2762) asks for measured Hz at the event; this puts it in the
    # record. Rides cmdFunc=254 cmdId=22, so it's absent on cmdId=21 frames (guarded).
    641: "grid_freq",  # Hz
    # Grid per-leg voltage/current (the grid-side metering block, distinct from the PCS
    # legs 1463-1468). Currents track load; useful cross-check for the grid-blip case.
    643: "grid_voltage_l1",  # V
    644: "grid_voltage_l2",  # V
    645: "grid_current_l1",  # A
    646: "grid_current_l2",  # A
    # DC-bus (DC-link) voltage — boosted ~5 V above battery terminal; diagnostic for the
    # grid-blip/islanding case. Two readings from the same status frame (cmdId=22).
    1502: "dc_bus_voltage",  # V
    1503: "dc_bus_voltage2",  # V
}

# Fault/status register slots — logged as codes (never averaged; see logger snapshot and
# CODE_METRICS). Only populated when the cmdId=22 status frame arrives, so low volume.
SYS_FIELDS.update({field: f"fault_{field}" for field in FAULT_FIELDS})

# Metrics that are codes/flags, not quantities: take the last value in a flush window
# rather than the mean (averaging a code invents states that never happened).
CODE_METRICS: frozenset[str] = frozenset({"work_mode", *(f"fault_{f}" for f in FAULT_FIELDS)})

# Battery-pack scalars, captured only from src=3/cmdFunc=32/cmdId=177 frames (see
# BATTERY_PACK_CMD): these field numbers are small and would collide with unrelated
# nested fields if matched on any frame. Not present in every capture — the pack stream
# is separate from the cmdFunc=254 inverter stream, so treat these as best-effort.
BATTERY_SYS_FIELDS: dict[int, str] = {
    11: "bp_soc",  # %   — real per-pack charge level
    44: "bp_power",  # W   — positive = charge, negative = discharge (confirmed vs SoC)
    43: "bp_current",  # dA  — logged so V*I can settle field 44's scale independently
    45: "bp_voltage_mv",  # mV
}
# Pack slot index, used to keep packs apart in a flush window: power and current add
# across packs, SOC and voltage average. Averaging power across packs would report one
# pack's draw as the whole bank's.
BATTERY_SLOT_FIELD = 5

# --- Ocean Smart Panel 40 (product type 95, likely HR61…) -------------------
# 40 circuits live in fields 1015–1054, each nested 1=voltage, 2=power, 3=active.
# Circuit index = field - 1014 (so 1015 -> circuit 1 … 1054 -> circuit 40).
PANEL_CIRCUIT_FIELDS = range(1015, 1055)
CIRCUIT_FIELD_BASE = 1014  # circuit_n lives at field CIRCUIT_FIELD_BASE + n
CIRCUIT_SUBFIELDS = {1: ("voltage", "V"), 2: ("power", "W"), 3: ("state", "")}
# Circuits that feed the inverter rather than a house load are install-specific — the
# panel names them "OCEAN Pro". Detect them by name (see names.py), don't hardcode
# positions (redawg's unit used 38/40; this one uses 37/39).
PANEL_FIELDS: dict[int, tuple[str, str, str]] = {
    # 270 was mislabelled "backup reserve". It is cms_max_chg_soc — the CHARGE CEILING —
    # confirmed against Delta3/DP3 protos and James's live config (read 80 = charge-to-80%).
    270: ("max_charge_soc", "%", "cms_max_chg_soc — charge ceiling (read 80 = charge to 80%)"),
    # Real backup reserve SOC. Field 461 read 30 in the live capture, matching James's
    # configured 30% reserve; the old 1215 label read 100 and was NOT the reserve.
    461: ("backup_reserve_soc", "%", "backup reserve SOC (read 30, matches configured 30%)"),
    467: ("panel_storm_guard_armed", "bool", "Storm Guard armed"),
    # NOT backup reserve (that's 461). Reads a steady 100; true meaning unconfirmed — likely a
    # display/SOC cap. Kept for annotation only, renamed off the wrong label.
    1215: ("panel_soc_100_1215", "%", "reads 100; NOT backup reserve — meaning unconfirmed"),
}

# --- EMS work-mode codes (field 1470) ---------------------------------------
# US app names, confirmed via live Self-powered <-> Intelligent toggles.
# EU PowerOcean docs use overlapping numbers (9 = TIMER_MODE there).
WORK_MODE_CODES: dict[int, str] = {
    0: "self_use",  # Self-powered
    1: "time_of_use",
    2: "backup",  # Emergency Backup
    3: "debug",
    4: "ac_makeup",
    5: "drm",
    6: "remote_schedule",
    7: "standby",
    8: "soc_calibration",
    9: "intelligent",  # Intelligent (app)
}

# --- Product-type header values ---------------------------------------------
PRODUCT_TYPES: dict[str, str] = {
    "83": "Power Ocean",
    "85": "Power Ocean DC Fit",
    "86": "Power Ocean Single Phase",
    "87": "Power Ocean Plus",
    "88": "Power Ocean Pro",
    "95": "Ocean Smart Panel 40",
    "99": "Ocean EV Charger",
}

# Serial-prefix -> control-message routing `dest` (klm-blip/ClaudeEcoFlow).
# Wrong dest = command silently ignored. Read-only telemetry doesn't need it.
DEST_BY_SN_PREFIX: dict[str, int] = {
    "HR5": 2,  # Ocean Pro inverter
    "HR6": 11,  # Ocean Smart Gateway / Panel
}


def describe_field(
    field: int, *, panel: bool = False, battery: bool = False
) -> tuple[str, str, str] | None:
    """Return (name, unit, note) for a protobuf leaf field number, or None.

    The inverter and panel maps use distinctive high field numbers, so they are safe
    to match by leaf number anywhere. The battery-pack fields are low numbers (3, 5,
    11, …) that collide with every other nested submessage, so they are only consulted
    when ``battery=True`` — i.e. when the caller already knows the path sits inside a
    cmdFunc=32/cmdId=177 pack block. Set ``panel=True`` for Ocean Smart Panel 40 data.
    """
    if panel:
        if field in PANEL_CIRCUIT_FIELDS:
            n = field - 1015 + 1
            return (f"circuit_{n}", "", "nested 1=voltage 2=power 3=active")
        if field in PANEL_FIELDS:
            return PANEL_FIELDS[field]
    if field in INVERTER_FIELDS:
        return INVERTER_FIELDS[field]
    if battery and field in BATTERY_PACK_FIELDS:
        return BATTERY_PACK_FIELDS[field]
    return None


def annotate_path(
    path: str, *, panel: bool = False, battery: bool = False
) -> str | None:
    """Annotate a dotted ``protodump`` path (e.g. ``1.1.515``) with its meaning.

    Returns a ``"name (unit) — note"`` string for the trailing field number, or None
    if that field isn't in the map. Only the leaf segment is matched. See
    :func:`describe_field` for why ``battery`` is opt-in.
    """
    segs = path.split(".")
    try:
        leaf = int(segs[-1])
    except ValueError:
        return None

    # Panel circuit nested subfield: <circuit 1015–1054>.<1=volt|2=power|3=state>.
    if panel and len(segs) >= 2 and leaf in CIRCUIT_SUBFIELDS:
        try:
            parent = int(segs[-2])
        except ValueError:
            parent = None
        if parent in PANEL_CIRCUIT_FIELDS:
            n = parent - CIRCUIT_FIELD_BASE
            sub, unit = CIRCUIT_SUBFIELDS[leaf]
            label = f"circuit_{n}_{sub}"
            return f"{label} ({unit})" if unit else label

    desc = describe_field(leaf, panel=panel, battery=battery)
    if desc is None:
        return None
    name, unit, note = desc
    label = f"{name} ({unit})" if unit else name
    return f"{label} — {note}" if note else label
