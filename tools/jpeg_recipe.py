#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, standard-library Fujifilm JPEG recipe metadata example.

The public entry point is parse_jpeg(bytes, *, wb_shift_scale='unknown').
No PTP operations, image decoding, camera support inference, or missing-value
defaults are performed. See docs/10-jpeg-recipes.md for the output contract.
MIT license; see tools/LICENSE. Mapping facts: ExifTool 13.55 FujiFilm.pm.
"""

import argparse
import json
from pathlib import Path
import struct
import sys

SCHEMA = "fujifilm-jpeg-recipe/1"
SOURCE = {
    "name": "ExifTool", "version": "13.55",
    "commit": "de11d240cf7e521e939a0575a128ffe01b63be05",
    "url": "https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm",
    "fuji_table_sha256": "01ac90924ee80c8111c87e0b8bc9d14b857c342224da3ad7b269e20177894a8e",
    "exif_url": "https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/Exif.pm",
    "exif_table_sha256": "8cd9bdb5211fbfd8e281c4879ccd587c896407f903dad57edae53684542b6989",
}
NAMES = {
    0x1001: "Sharpness", 0x1002: "WhiteBalance", 0x1003: "Saturation",
    0x1005: "ColorTemperature", 0x100A: "WhiteBalanceFineTune",
    0x100E: "NoiseReduction", 0x100F: "Clarity", 0x1040: "ShadowTone",
    0x1041: "HighlightTone", 0x1045: "LensModulationOptimizer",
    0x1047: "GrainEffectRoughness", 0x1048: "ColorChromeEffect",
    0x1049: "BWAdjustment", 0x104B: "BWMagentaGreen", 0x104C: "GrainEffectSize",
    0x104D: "CropMode", 0x104E: "ColorChromeFXBlue", 0x1050: "ShutterType",
    0x1401: "FilmMode", 0x1402: "DynamicRangeSetting",
    0x1403: "DevelopmentDynamicRange", 0x140B: "AutoDynamicRange",
    0x1443: "DRangePriority", 0x1444: "DRangePriorityAuto", 0x1445: "DRangePriorityFixed",
}
SHARPNESS = {0: -4, 1: -3, 2: -2, 0x82: -1, 3: 0, 0x84: 1, 4: 2, 5: 3, 6: 4}
COLOR = {0: 0, 0x80: 1, 0x100: 2, 0xC0: 3, 0xE0: 4, 0x180: -1,
         0x400: -2, 0x4C0: -3, 0x4E0: -4}
MONO = {0x300: "monochrome", 0x301: "monochrome_red", 0x302: "monochrome_yellow",
        0x303: "monochrome_green", 0x310: "sepia", 0x500: "acros",
        0x501: "acros_red", 0x502: "acros_yellow", 0x503: "acros_green"}
FILM = {0: "provia", 0x100: "f1_studio_portrait", 0x110: "f1a_studio_portrait",
        0x120: "astia", 0x130: "f1c_studio_portrait", 0x200: "velvia",
        0x300: "f3_studio_portrait_ex", 0x400: "velvia", 0x500: "pro_neg_std",
        0x501: "pro_neg_hi", 0x600: "classic_chrome", 0x700: "eterna",
        0x800: "classic_negative", 0x900: "eterna_bleach_bypass",
        0xA00: "nostalgic_negative", 0xB00: "reala_ace"}
WB = {0: "auto", 1: "auto_white_priority", 2: "auto_ambience_priority",
      0x100: "daylight", 0x200: "cloudy", 0x300: "daylight_fluorescent",
      0x301: "day_white_fluorescent", 0x302: "white_fluorescent",
      0x303: "warm_white_fluorescent", 0x304: "living_room_warm_white_fluorescent",
      0x400: "incandescent", 0x500: "flash", 0x600: "underwater",
      0xF00: "custom_1", 0xF01: "custom_2", 0xF02: "custom_3",
      0xF03: "custom_4", 0xF04: "custom_5", 0xFF0: "kelvin"}
NR = {0: 0, 0x180: 1, 0x100: 2, 0x1C0: 3, 0x1E0: 4,
      0x280: -1, 0x200: -2, 0x2C0: -3, 0x2E0: -4}
EFFECT = {0: "off", 32: "weak", 64: "strong"}
_TYPES = {1: (1, "B"), 2: (1, None), 3: (2, "H"), 4: (4, "I"),
          5: (8, None), 6: (1, "b"), 7: (1, "B"), 8: (2, "h"),
          9: (4, "i"), 10: (8, None), 11: (4, "f"), 12: (8, "d")}
_ALLOWED = {"IFD0": {0x10F: "Make", 0x110: "Model"},
            "ExifIFD": {0xA001: "ColorSpace"}, "InteropIFD": {1: "InteropIndex"},
            "FujiFilm": NAMES}
_SCALES = ("unknown", "direct", "times20", "heuristic")


class _Malformed(ValueError):
    pass


def _check(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise _Malformed("value or directory exceeds its enclosing metadata region")


def _ifd(data, offset, order, group, *, next_pointer=True):
    """Offsets are relative to data, never to an enclosing JPEG/file buffer."""
    _check(data, offset, 2)
    count = struct.unpack_from(order + "H", data, offset)[0]
    if count > 4096:
        raise _Malformed("IFD entry count exceeds the parser limit")
    _check(data, offset + 2, count * 12 + (4 if next_pointer else 0))
    entries = []
    for index in range(count):
        pos = offset + 2 + index * 12
        tag, kind, length = struct.unpack_from(order + "HHI", data, pos)
        item = {"group": group, "tag": f"0x{tag:04x}", "type": kind,
                "count": length, "entry_offset": pos, "status": "read"}
        item["name"] = _ALLOWED.get(group, {}).get(tag, "unexported")
        if kind not in _TYPES:
            item["status"] = "unsupported_type"
        else:
            size, code = _TYPES[kind]
            size *= length
            start = pos + 8 if size <= 4 else struct.unpack_from(order + "I", data, pos + 8)[0]
            item["storage"] = "inline" if size <= 4 else "offset"
            item["value_offset"] = start
            try:
                _check(data, start, size)
                item["_bytes"] = data[start:start + size]
                if length == 0:
                    item["status"] = "empty"
                elif size > 256 and not (group == "ExifIFD" and tag == 0x927C):
                    item["status"] = "value_too_large"
                elif kind == 2:
                    item["_value"] = item["_bytes"].split(b"\0", 1)[0].decode("ascii", "replace")
                elif code is not None and length <= 256:
                    values = list(struct.unpack(order + str(length) + code, item["_bytes"]))
                    item["_value"] = values[0] if length == 1 else values
                elif group == "ExifIFD" and tag == 0x927C:
                    pass  # opaque MakerNote bytes, parsed in their own bounded region
                else:
                    item["status"] = "unsupported_type"
            except _Malformed:
                item["status"] = "out_of_bounds"
        entries.append(item)
    return entries


def _one(entries, group, tag):
    candidates = [e for e in entries if e["group"] == group and e["tag"] == f"0x{tag:04x}"]
    if not candidates:
        return None, "missing"
    if len(candidates) != 1:
        return None, "ambiguous"
    entry = candidates[0]
    if entry["status"] != "read":
        return entry, "malformed"
    return entry, "decoded"


def _pointer(entries, group, tag):
    entry, state = _one(entries, group, tag)
    if state == "missing":
        return None
    if state != "decoded" or entry["type"] != 4 or entry["count"] != 1:
        raise _Malformed("invalid or duplicate IFD pointer")
    return entry["_value"]


def _jpeg_exif(data):
    if not data.startswith(b"\xff\xd8"):
        return [], "invalid_jpeg", "missing JPEG SOI marker"
    position, found = 2, []
    while position < len(data):
        if data[position] != 0xFF:
            return found, "partial", "invalid JPEG marker before image scan"
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position == len(data):
            return found, "partial", "truncated JPEG marker"
        marker = data[position]
        position += 1
        if marker in (0xD9, 0xDA):  # do not scan entropy-coded pixels
            return found, None, None
        if marker in (0, 0xD8) or 0xD0 <= marker <= 0xD7:
            return found, "partial", "unexpected standalone marker before image scan"
        if marker == 1:  # TEM has no length field
            continue
        if position + 2 > len(data):
            return found, "partial", "truncated JPEG segment length"
        size = struct.unpack_from(">H", data, position)[0]
        if size < 2 or position + size > len(data):
            return found, "partial", "truncated or invalid JPEG segment"
        payload = data[position + 2:position + size]
        if marker == 0xE1 and payload.startswith(b"Exif\0\0"):
            found.append((position + 8, payload[6:]))
            if len(found) > 1:
                return found, "malformed_exif", "multiple EXIF APP1 segments are ambiguous"
        position += size
    return found, "partial", "JPEG ends before SOS or EOI; only complete metadata segments were read"


def _field(status, tags, value=None, **extra):
    result = {"status": status, "tags": tags}
    if status == "decoded":
        result["value"] = value
        result["basis"] = "published_mapping"
    result.update(extra)
    return result


def _normalize(entries, scale):
    def get(tag, group="FujiFilm", array=False):
        entry, state = _one(entries, group, tag)
        tags = [f"{group}:0x{tag:04x}"]
        if state != "decoded":
            return _field(state, tags)
        value = entry.get("_value")
        if array:
            valid = entry["type"] == 9 and isinstance(value, list) and len(value) == 2
        elif group in ("IFD0", "InteropIFD"):
            valid = entry["type"] == 2 and isinstance(value, str)
        else:
            valid = type(value) is int and entry["type"] in (1, 3, 4, 6, 7, 8, 9)
        if not valid:
            return _field("malformed", tags, reason="unexpected value type or count")
        if group == "FujiFilm" and tag in (0x1049, 0x104B):
            # ExifTool explicitly overrides these tags to int8s. Real notes may
            # declare a larger TIFF integer; interpretation uses the first byte.
            value = struct.unpack("b", entry["_bytes"][:1])[0]
            return _field("decoded", tags, value, basis="published_int8s_override")
        return _field("decoded", tags, value)

    def mapped(tag, table, group="FujiFilm"):
        field = get(tag, group)
        if field["status"] == "decoded":
            value = field.pop("value")
            if value in table:
                field["value"] = table[value]
            else:
                field.update(status="unrecognized", raw_value=value)
        return field

    recipe = {}
    sat = get(0x1003)
    sat_value = sat.get("value")
    if sat["status"] == "decoded" and sat_value in MONO:
        recipe["film_simulation"] = mapped(0x1003, MONO)
        recipe["color"] = _field("inactive", sat["tags"], reason="monochrome simulation")
    else:
        recipe["film_simulation"] = mapped(0x1401, FILM)
        # Saturation also identifies monochrome. Missing/unknown/duplicate
        # Saturation prevents an unconditional color FilmMode interpretation.
        if sat["status"] != "decoded" or sat_value not in COLOR:
            film = recipe["film_simulation"]
            if film["status"] == "decoded":
                film.update(status="unresolved", candidate=film.pop("value"),
                            reason="Saturation does not rule out a monochrome override")
        recipe["color"] = mapped(0x1003, COLOR)
    for name, tag, table in (
        ("sharpness", 0x1001, SHARPNESS), ("high_iso_noise_reduction", 0x100E, NR),
        ("color_chrome_effect", 0x1048, EFFECT), ("color_chrome_fx_blue", 0x104E, EFFECT),
        ("grain_strength", 0x1047, EFFECT), ("grain_size", 0x104C, {0: "off", 16: "small", 32: "large"}),
        ("white_balance", 0x1002, WB),
    ):
        recipe[name] = mapped(tag, table)
    for name, tag in (("shadow_tone", 0x1040), ("highlight_tone", 0x1041)):
        field = get(tag)
        if field["status"] == "decoded":
            field["value"] = -field["value"] / 16
            field["basis"] = "published_formula"
        recipe[name] = field
    recipe["clarity"] = mapped(0x100F, {i * 1000: i for i in range(-5, 6)})
    for name, tag in (("monochromatic_color_wc", 0x1049), ("monochromatic_color_mg", 0x104B)):
        recipe[name] = get(tag)
        recipe[name]["applicability"] = "monochrome_only; recorded value may be inactive"
    if recipe["grain_strength"].get("value") == "off":
        size = recipe["grain_size"]
        recipe["grain_size"] = _field("inactive", size["tags"], reason="grain strength is off",
                                      recorded=size)
    elif recipe["grain_size"].get("value") == "off" and recipe["grain_strength"].get("value") in ("weak", "strong"):
        recipe["grain_size"].update(status="unresolved", reason="nonzero grain strength with size Off")
        recipe["grain_size"]["recorded_value"] = recipe["grain_size"].pop("value")
    if recipe["white_balance"].get("value", "").startswith("custom_"):
        recipe["white_balance"]["portability"] = "slot identity only; measured white balance is not reconstructed"
    recipe["white_balance_kelvin"] = get(0x1005)
    recipe["white_balance_kelvin"]["applicability"] = "kelvin_mode_only"
    shifts = get(0x100A, array=True)
    if shifts["status"] == "decoded":
        pair = shifts.pop("value")
        selected = scale
        if scale == "heuristic":
            selected = "times20" if max(map(abs, pair)) > 9 else "direct"
        divisor = {"direct": 1, "times20": 20}.get(selected)
        shifts.update(raw_value=pair, scale_policy=scale)
        if divisor is None:
            shifts.update(status="unresolved", reason="body-specific WB shift scale is not established")
        elif any(v % divisor or abs(v // divisor) > 9 for v in pair):
            shifts.update(status="unresolved", reason="pair is not integral and within ±9 under selected scale")
        else:
            shifts["value"] = {"red": pair[0] // divisor, "blue": pair[1] // divisor}
            shifts["basis"] = "explicit_heuristic" if scale == "heuristic" else "caller_selected_scale"
            shifts["divisor"] = divisor
    recipe["white_balance_shift"] = shifts

    dr = get(0x1402)
    if dr["status"] == "decoded":
        raw = dr.pop("value")
        if raw == 0:
            dr["value"] = {"mode": "auto"}
        elif raw == 1:
            percent = get(0x1403)
            dr["tags"] += percent["tags"]
            if percent["status"] == "decoded" and percent["value"] in (100, 200, 400):
                dr["value"] = {"mode": "manual", "percent": percent["value"]}
            else:
                dr.update(status="unresolved", mode="manual", development=percent,
                          reason="manual DR percentage missing, malformed, or outside non-HDR recipe set")
        elif raw in (0x100, 0x201):
            dr["value"] = {"mode": "manual", "percent": {0x100: 100, 0x201: 400}[raw]}
        else:
            dr.update(status="unresolved" if raw in (0x200, 0x8000) else "unrecognized", raw_value=raw)
            if raw == 0x200:
                dr.update(published_label="Wide1 (230%)", reason="legacy label is not a portable DR200 setting")
            elif raw == 0x8000:
                dr.update(published_label="Film Simulation", reason="original numeric DR intent is not recoverable")
    recipe["dynamic_range"] = dr
    priority = mapped(0x1443, {0: "auto", 1: "fixed"})
    mode = priority.get("value")
    if mode is not None:
        priority["value"] = {"mode": mode}
        strength = mapped(0x1444 if mode == "auto" else 0x1445,
                          {1: "weak", 2: "strong", **({3: "plus"} if mode == "auto" else {})})
        priority["strength"] = strength
        if mode == "fixed" and strength["status"] != "decoded":
            priority.update(status="unresolved", reason="fixed priority strength is not recoverable",
                            mode=mode)
            priority.pop("value")
    recipe["d_range_priority"] = priority
    if mode in ("auto", "fixed"):
        for name in ("dynamic_range", "highlight_tone", "shadow_tone"):
            recipe[name]["applicability"] = "priority-controlled; recorded value is not independent recipe intent"

    observations = {
        "development_dynamic_range": get(0x1403), "auto_dynamic_range": get(0x140B),
        "lens_modulation_optimizer": mapped(0x1045, {0: "off", 1: "on"}),
        "crop_mode": mapped(0x104D, {0: "not_applicable", 1: "full_frame_on_gfx", 2: "sports_finder",
                                     4: "electronic_shutter_1_25_crop", 8: "digital_teleconverter"}),
        "shutter_type": mapped(0x1050, {0: "mechanical", 1: "electronic", 2: "electronic_long_exposure",
                                        3: "electronic_front_curtain"}),
    }
    observations["development_dynamic_range"]["applicability"] = "manual DR; HDR can use other percentages"
    observations["auto_dynamic_range"]["applicability"] = "Auto's selected percentage, not user's manual setting"
    space, interop = get(0xA001, "ExifIFD"), get(1, "InteropIFD")
    observations["exif_color_space"] = space
    observations["interop_index"] = interop
    cs, ix = space.get("value"), interop.get("value")
    tags = space["tags"] + interop["tags"]
    if "ambiguous" in (space["status"], interop["status"]):
        observations["color_space"] = _field("ambiguous", tags, reason="duplicate color-space metadata")
    elif "malformed" in (space["status"], interop["status"]):
        observations["color_space"] = _field("unresolved", tags, reason="malformed color-space metadata")
    elif (cs == 1 and ix == "R03") or (cs == 2 and ix == "R98"):
        observations["color_space"] = _field("ambiguous", tags, reason="ColorSpace and InteropIndex conflict")
    elif cs == 1 or (cs in (None, 65535) and ix == "R98"):
        observations["color_space"] = _field("decoded", tags, "srgb")
    elif cs == 2 or (cs in (None, 65535) and ix == "R03"):
        observations["color_space"] = _field("decoded", tags, "adobe_rgb")
        if cs == 2:
            observations["color_space"]["note"] = "ColorSpace=2 is a non-standard EXIF convention"
    else:
        observations["color_space"] = _field("missing" if space["status"] == interop["status"] == "missing" else "unresolved", tags)
    camera = {"make": get(0x10F, "IFD0"), "model": get(0x110, "IFD0")}
    return recipe, observations, camera


def parse_jpeg(data: bytes, *, wb_shift_scale="unknown") -> dict:
    """Return bounded, privacy-filtered raw metadata and semantic interpretations.

    Malformed image bytes become a result status/issues, not an exception. Wrong
    Python argument types/unsupported scale options raise TypeError/ValueError.
    An 'ok' status describes metadata parsing only, never complete JPEG pixels.
    """
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if wb_shift_scale not in _SCALES:
        raise ValueError("unsupported white-balance shift scale")
    entries, issues = [], []
    result = {"schema": SCHEMA, "status": "no_exif", "mapping_source": dict(SOURCE),
              "input": {"format": "jpeg", "bytes": len(data), "pixels_validated": False},
              "privacy": "allowlisted recipe metadata; unrecognized tags have no exported payload"}
    segments, scan_status, scan_issue = _jpeg_exif(data)
    if scan_issue:
        issues.append(scan_issue)
    if scan_status == "invalid_jpeg":
        result["status"] = scan_status
    elif len(segments) > 1:
        result["status"] = "malformed_exif"
    elif segments:
        file_offset, tiff = segments[0]
        result["input"]["exif_tiff_offset"] = file_offset
        result["input"]["exif_tiff_bytes"] = len(tiff)
        try:
            _check(tiff, 0, 8)
            order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
            if order is None or struct.unpack_from(order + "H", tiff, 2)[0] != 42:
                raise _Malformed("invalid TIFF byte order or magic")
            result["input"]["tiff_byte_order"] = "little" if order == "<" else "big"
            first = struct.unpack_from(order + "I", tiff, 4)[0]
            if first < 8:
                raise _Malformed("IFD0 points into the TIFF header")
            visited = {first}
            entries += _ifd(tiff, first, order, "IFD0")
            exif = _pointer(entries, "IFD0", 0x8769)
            if exif is not None:
                if exif < 8 or exif in visited:
                    raise _Malformed("invalid or cyclic ExifIFD pointer")
                visited.add(exif)
                entries += _ifd(tiff, exif, order, "ExifIFD")
                interop = _pointer(entries, "ExifIFD", 0xA005)
                if interop is not None:
                    if interop < 8 or interop in visited:
                        raise _Malformed("invalid or cyclic InteropIFD pointer")
                    entries += _ifd(tiff, interop, order, "InteropIFD")
            maker, state = _one(entries, "ExifIFD", 0x927C)
            result["status"] = "no_fujifilm_makernote"
            if state not in ("missing", "decoded"):
                raise _Malformed("malformed or duplicate MakerNote tag")
            if maker is not None:
                if maker["type"] != 7:
                    raise _Malformed("MakerNote must have TIFF UNDEFINED type")
                note = maker.get("_bytes", b"")
                if note.startswith(b"FUJIFILM"):
                    _check(note, 0, 12)
                    offset = struct.unpack_from("<I", note, 8)[0]
                    if offset < 12:
                        raise _Malformed("MakerNote IFD points into the Fujifilm header")
                    entries += _ifd(note, offset, "<", "FujiFilm", next_pointer=False)
                    result["input"]["maker_note_byte_order"] = "little"
                    result["input"]["maker_note_bytes"] = len(note)
                    result["status"] = "ok"
        except _Malformed as error:
            result["status"] = "malformed_exif"
            issues.append(str(error))
        if result["status"] == "ok" and (scan_status or any(e["status"] != "read" for e in entries if e["name"] != "unexported")):
            result["status"] = "partial"
    elif scan_status:
        result["status"] = "invalid_jpeg"
    result["recipe"], result["observations"], result["camera"] = _normalize(entries, wb_shift_scale)
    result["raw_tags"] = []
    for entry in entries:
        exported = {key: value for key, value in entry.items() if not key.startswith("_")}
        if entry["name"] == "unexported":
            exported["status"] = "not_exported"
        elif "_value" in entry:
            # Avoid arbitrary binary/string payloads hidden under numeric tag IDs.
            expected_text = entry["group"] in ("IFD0", "InteropIFD") and entry["type"] == 2
            expected_number = entry["group"] in ("FujiFilm", "ExifIFD") and entry["type"] in (1, 3, 4, 6, 7, 8, 9)
            if expected_text or expected_number:
                exported["value"] = entry["_value"]
            else:
                exported["status"] = "unexpected_type_payload_not_exported"
        result["raw_tags"].append(exported)
    result["issues"] = issues
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jpeg", type=Path, help="JPEG or metadata-only JPEG envelope; opened read-only")
    parser.add_argument("--wb-shift-scale", choices=_SCALES, default="unknown",
                        help="explicit interpretation policy; default preserves an unresolved raw pair")
    args = parser.parse_args(argv)
    try:
        result = parse_jpeg(args.jpeg.read_bytes(), wb_shift_scale=args.wb_shift_scale)
    except OSError as error:
        # Do not echo private paths into machine-readable output.
        print(json.dumps({"schema": SCHEMA, "status": "io_error", "error": error.strerror}))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
    return 2 if result["status"] in ("invalid_jpeg", "malformed_exif") else 0


if __name__ == "__main__":
    sys.exit(main())
