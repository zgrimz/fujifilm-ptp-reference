#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic metadata-only JPEG envelopes. No camera or image pixels involved.

This fixture writer is deliberately separate from the parser; its test values
are hand-selected from published metadata definitions. Run from any directory.
"""
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent


def _encoded(kind, value, order):
    if kind in (2, 7):
        return bytes(value), len(value)
    values = value if isinstance(value, (tuple, list)) else [value]
    code = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f"}[kind]
    return struct.pack(order + str(len(values)) + code, *values), len(values)


def maker_note(tags):
    blob = bytearray(b"FUJIFILM" + struct.pack("<I", 12))
    blob.extend(struct.pack("<H", len(tags)) + bytes(len(tags) * 12 + 4))
    for index, (tag, kind, value) in enumerate(tags):
        raw, count = _encoded(kind, value, "<")
        pos = 14 + index * 12
        struct.pack_into("<HHI", blob, pos, tag, kind, count)
        if len(raw) <= 4:
            blob[pos + 8:pos + 8 + len(raw)] = raw
        else:
            if len(blob) % 2:
                blob.append(0)
            struct.pack_into("<I", blob, pos + 8, len(blob))
            blob.extend(raw)
    return bytes(blob)


def make_jpeg(tags, *, order="<", color_space=1, interop=b"R98\0", model=b"SYNTHETIC FIXTURE\0"):
    note = maker_note(tags)
    # Fixed, independent directory placement makes malformed offset tests clear.
    root, exif, io = 8, 50, 92
    blob = bytearray((b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, root))
    blob.extend(bytes(110 - len(blob)))

    def directory(offset, entries):
        struct.pack_into(order + "H", blob, offset, len(entries))
        for index, (tag, kind, value) in enumerate(entries):
            raw, count = _encoded(kind, value, order)
            pos = offset + 2 + index * 12
            struct.pack_into(order + "HHI", blob, pos, tag, kind, count)
            if len(raw) <= 4:
                blob[pos + 8:pos + 8 + len(raw)] = raw
            else:
                if len(blob) % 2:
                    blob.append(0)
                struct.pack_into(order + "I", blob, pos + 8, len(blob))
                blob.extend(raw)
        struct.pack_into(order + "I", blob, offset + 2 + len(entries) * 12, 0)

    directory(root, [(0x10F, 2, b"FUJIFILM\0"), (0x110, 2, model), (0x8769, 4, exif)])
    directory(exif, [(0x927C, 7, note), (0xA001, 3, color_space), (0xA005, 4, io)])
    directory(io, [(1, 2, interop)])
    payload = b"Exif\0\0" + bytes(blob)
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + b"\xff\xd9"


CASES = {
    "synthetic-le-acros-red": {
        "tags": [(0x1001, 3, 0x82), (0x1002, 3, 0xFF0), (0x1003, 3, 0x501),
                 (0x1005, 3, 5300), (0x100A, 9, [60, -40]), (0x100E, 3, 0x2E0),
                 (0x100F, 9, -3000), (0x1040, 9, -24), (0x1041, 9, 8),
                 (0x1045, 4, 1), (0x1047, 9, 32), (0x1048, 9, 64),
                 (0x1049, 1, 238), (0x104B, 1, 18), (0x104C, 3, 32),
                 (0x104E, 9, 32), (0x1401, 3, 0), (0x1402, 3, 1),
                 (0x1403, 3, 400), (0x1443, 3, 1), (0x1445, 3, 2)],
        "covers": ["little-endian TIFF", "ACROS Red", "unsigned-declared signed8 toning", "half tones",
                   "indirect signed WB pair", "grain strength and size", "manual DR", "fixed priority"],
    },
    "synthetic-be-acros-yellow": {
        "tags": [(0x1001, 3, 3), (0x1002, 3, 1), (0x1003, 3, 0x502),
                 (0x100A, 9, [-2, 5]), (0x1040, 9, 32), (0x1041, 9, -64),
                 (0x1049, 6, -5), (0x104B, 6, 7), (0x1047, 9, 0),
                 (0x104C, 3, 16), (0x1401, 3, 0), (0x1402, 3, 0),
                 (0x1403, 3, 100), (0x140B, 3, 200), (0x1443, 3, 0), (0x1444, 3, 3)],
        "options": {"order": ">", "color_space": 65535, "interop": b"R03\0"},
        "covers": ["big-endian TIFF with little-endian MakerNote", "ACROS Yellow", "signed-byte toning",
                   "Auto DR separate from stale manual percentage", "Auto priority Plus", "Adobe RGB Interop"],
    },
    "synthetic-color-and-unknown": {
        "tags": [(0x0010, 2, b"PRIVATE-SERIAL-DO-NOT-EXPORT\0"), (0x1001, 3, 0x8000),
                 (0x1002, 3, 0xF02), (0x1003, 3, 0x4E0), (0x1047, 9, 64),
                 (0x1048, 9, 12345), (0x1401, 3, 0xB00), (0x1402, 3, 0x200),
                 (0x7FFE, 2, b"PRIVATE-OWNER-DO-NOT-EXPORT\0")],
        "covers": ["color film", "custom WB slot only", "missing grain size", "unknown effect value",
                   "legacy Wide1 ambiguity", "serial and unknown-text suppression"],
    },
    "synthetic-missing": {"tags": [], "covers": ["all Fuji recipe tags missing; no defaults"]},
}


def main():
    manifest = {"schema": "jpeg-fixture-manifest/1", "evidence": "synthetic",
                "camera_or_firmware": None, "pixels": "absent; metadata-only JPEG envelopes",
                "generator": "generate_synthetic.py", "files": []}
    for name, case in CASES.items():
        data = make_jpeg(case["tags"], **case.get("options", {}))
        path = HERE / (name + ".jpg")
        path.write_bytes(data)
        manifest["files"].append({"path": path.name, "bytes": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest(), "covers": case["covers"]})
    (HERE / "synthetic-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
