"""Decode captured Ocean Pro frames without a .proto schema.

Protobuf's wire format is self-describing enough to recover field numbers, wire types
and values. That is sufficient to map fields to real quantities by watching which
numbers move with load, and to hand-write a .proto later.

    python3 protodump.py [capture.jsonl] [--sn SN] [--summary]

Zero dependencies (standard library only). Supply your own capture: a JSONL file of
records like {"topic": ".../<sn>", "kind": "hex", "payload": "<hex protobuf>"} — one per
MQTT message. With no path it looks for capture-*.jsonl in a ./captures directory.
"""

from __future__ import annotations

import json
import pathlib
import struct
import sys
from collections import defaultdict

try:  # runs both as a package module and as a loose script from the repo root
    from .fieldmap import annotate_path
except ImportError:
    from fieldmap import annotate_path

OUT_DIR = pathlib.Path(__file__).resolve().parent / "captures"


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while pos < len(buf):
        byte = buf[pos]
        result |= (byte & 0x7F) << shift
        pos += 1
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 63:
            break
    raise ValueError("varint overrun")


def looks_like_message(buf: bytes) -> bool:
    """Cheap check: does this blob parse cleanly as a nested message?"""
    try:
        return bool(list(parse(buf, depth=0, probe=True)))
    except (ValueError, IndexError, struct.error):
        return False


def parse(buf: bytes, depth: int = 0, probe: bool = False):
    """Yield (field_number, wire_type, value) triples; recurse into submessages."""
    pos = 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        field, wire = key >> 3, key & 0x07
        if field == 0:
            raise ValueError("field 0")
        if wire == 0:
            value, pos = read_varint(buf, pos)
        elif wire == 1:
            if pos + 8 > len(buf):
                raise ValueError("truncated 64-bit")
            raw = buf[pos : pos + 8]
            value = {
                "u64": struct.unpack("<Q", raw)[0],
                "f64": struct.unpack("<d", raw)[0],
            }
            pos += 8
        elif wire == 2:
            length, pos = read_varint(buf, pos)
            if pos + length > len(buf):
                raise ValueError("truncated bytes")
            raw = buf[pos : pos + length]
            pos += length
            if probe:
                value = raw
            elif depth < 6 and length and looks_like_message(raw):
                value = list(parse(raw, depth + 1))
            else:
                try:
                    text = raw.decode("ascii")
                    value = text if text.isprintable() else raw.hex()
                except UnicodeDecodeError:
                    value = raw.hex()
        elif wire == 5:
            if pos + 4 > len(buf):
                raise ValueError("truncated 32-bit")
            raw = buf[pos : pos + 4]
            value = {
                "u32": struct.unpack("<I", raw)[0],
                "f32": round(struct.unpack("<f", raw)[0], 4),
            }
            pos += 4
        else:
            raise ValueError(f"bad wire type {wire}")
        yield field, wire, value


def render(items, indent: int = 0) -> str:
    lines = []
    pad = "  " * indent
    for field, wire, value in items:
        if isinstance(value, list):
            lines.append(f"{pad}{field} (msg):")
            lines.append(render(value, indent + 1))
        else:
            lines.append(f"{pad}{field} (w{wire}): {value}")
    return "\n".join(lines)


def flatten_paths(items, prefix: str = "") -> dict:
    """field-path -> value, for spotting which fields vary between frames."""
    out = {}
    for field, wire, value in items:
        path = f"{prefix}.{field}" if prefix else str(field)
        if isinstance(value, list):
            out.update(flatten_paths(value, path))
        elif isinstance(value, dict):
            out[path] = value.get("f32", value.get("f64"))
        else:
            out[path] = value
    return out


def main() -> None:
    argv = sys.argv[1:]
    summary = "--summary" in argv
    argv = [a for a in argv if a != "--summary"]
    sn_filter = None
    if "--sn" in argv:
        i = argv.index("--sn")
        sn_filter = argv[i + 1]
        argv = argv[:i] + argv[i + 2 :]

    if argv:
        path = pathlib.Path(argv[0])
    else:
        caps = sorted(OUT_DIR.glob("capture-*.jsonl"))
        if not caps:
            sys.exit("no captures found — pass a capture .jsonl path, or put capture-*.jsonl in ./captures")
        path = caps[-1]
    print(f"# {path.name}\n")

    values: dict[str, set] = defaultdict(set)
    shown = 0
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("kind") != "hex":
            continue
        if sn_filter and sn_filter not in rec["topic"]:
            continue
        buf = bytes.fromhex(rec["payload"])
        try:
            items = list(parse(buf))
        except (ValueError, IndexError, struct.error) as exc:
            print(f"  [unparsed {len(buf)}B: {exc}]")
            continue
        for key, val in flatten_paths(items).items():
            if isinstance(val, (int, float, str)):
                values[key].add(val)
        if not summary and shown < 3:
            print(f"--- {rec['topic']} ({len(buf)}B)\n{render(items)}\n")
            shown += 1

    # HR6… serials are the Ocean Smart Panel 40; anything else is the inverter.
    panel = bool(sn_filter and sn_filter.upper().startswith("HR6"))

    known = sum(1 for k in values if annotate_path(k, panel=panel))
    print(f"\n# {len(values)} distinct field paths ({known} mapped)\n")
    print(f"{'path':<24} {'n':>4}  {'meaning':<40} sample values")
    for key in sorted(values, key=lambda k: (-len(values[k]), k)):
        vals = sorted(values[key], key=str)[:4]
        preview = ", ".join(str(v)[:18] for v in vals)
        meaning = annotate_path(key, panel=panel) or ""
        print(f"{key:<24} {len(values[key]):>4}  {meaning:<40} {preview}")


if __name__ == "__main__":
    main()
