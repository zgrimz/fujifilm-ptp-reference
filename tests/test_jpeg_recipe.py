# SPDX-License-Identifier: MIT
"""Parser/interpretation regression tests; synthetic tests are not camera evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from jpeg_recipe import parse_jpeg

_spec = importlib.util.spec_from_file_location("jpeg_fixture_generator", ROOT / "fixtures/jpeg/generate_synthetic.py")
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
make_jpeg = _fixture.make_jpeg
FIXTURES = ROOT / "fixtures/jpeg"


def fixture(name, **kwargs):
    return parse_jpeg((FIXTURES / (name + ".jpg")).read_bytes(), **kwargs)


class SyntheticExifLayout:
    """Locate mutation targets independently of jpeg_recipe's parser.

    This only describes the single-APP1 synthetic writer used by these tests.
    Read and verify tags/types/counts before editing; do not guess file offsets.
    """

    def __init__(self, data):
        self.data = data
        assert data[:4] == b"\xff\xd8\xff\xe1"
        assert data[6:12] == b"Exif\0\0"
        self.tiff_start = 12
        self.app1_end = 4 + struct.unpack_from(">H", data, 4)[0]
        assert self.app1_end <= len(data)
        self.order = {b"II": "<", b"MM": ">"}[bytes(data[12:14])]
        assert self.unpack("H", self.tiff_start + 2) == 42
        self.root = self.unpack("I", self.tiff_start + 4)

    def unpack(self, kind, offset):
        return struct.unpack_from(self.order + kind, self.data, offset)[0]

    def entry(self, directory, tag):
        start = self.tiff_start + directory
        count = self.unpack("H", start)
        assert start + 2 + count * 12 + 4 <= self.app1_end
        matches = [start + 2 + index * 12 for index in range(count)
                   if self.unpack("H", start + 2 + index * 12) == tag]
        assert len(matches) == 1, f"expected one synthetic entry for {tag:#x}"
        return matches[0]

    def exif_entry(self, tag):
        pointer = self.entry(self.root, 0x8769)
        assert self.unpack("H", pointer + 2) == 4
        assert self.unpack("I", pointer + 4) == 1
        return self.entry(self.unpack("I", pointer + 8), tag)


def raw_tag(result, group, tag):
    matches = [entry for entry in result["raw_tags"]
               if (entry["group"], entry["tag"]) == (group, tag)]
    assert len(matches) == 1
    return matches[0]


def at_path(value, path):
    for component in path:
        value = value[component]
    return value


class JPEGRecipeTests(unittest.TestCase):
    def test_little_endian_signed_and_fractional(self):
        result = fixture("synthetic-le-acros-red", wb_shift_scale="times20")
        self.assertEqual(result["status"], "ok")
        r = result["recipe"]
        expected = {"film_simulation": "acros_red", "sharpness": -1,
                    "monochromatic_color_wc": -18, "monochromatic_color_mg": 18,
                    "highlight_tone": -0.5, "shadow_tone": 1.5,
                    "grain_strength": "weak", "grain_size": "large", "clarity": -3,
                    "high_iso_noise_reduction": -4, "white_balance_kelvin": 5300,
                    "white_balance_shift": {"red": 3, "blue": -2},
                    "dynamic_range": {"mode": "manual", "percent": 400}}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(r[key]["value"], value)
        self.assertEqual(r["color"]["status"], "inactive")
        self.assertEqual(r["d_range_priority"]["strength"]["value"], "strong")
        self.assertEqual(result["observations"]["lens_modulation_optimizer"]["value"], "on")
        self.assertFalse(result["input"]["pixels_validated"])

    def test_big_outer_little_maker_and_auto_separation(self):
        result = fixture("synthetic-be-acros-yellow", wb_shift_scale="direct")
        r = result["recipe"]
        self.assertEqual(result["input"]["tiff_byte_order"], "big")
        self.assertEqual(result["input"]["maker_note_byte_order"], "little")
        self.assertEqual(r["film_simulation"]["value"], "acros_yellow")
        self.assertEqual(r["monochromatic_color_wc"]["value"], -5)
        self.assertEqual(r["dynamic_range"]["value"], {"mode": "auto"})
        self.assertEqual(result["observations"]["development_dynamic_range"]["value"], 100)
        self.assertEqual(result["observations"]["auto_dynamic_range"]["value"], 200)
        self.assertEqual(r["d_range_priority"]["value"], {"mode": "auto"})
        self.assertEqual(r["d_range_priority"]["strength"]["value"], "plus")
        self.assertEqual(r["grain_size"]["status"], "inactive")
        self.assertEqual(result["observations"]["color_space"]["value"], "adobe_rgb")

    def test_missing_is_never_off_or_zero(self):
        result = fixture("synthetic-missing")
        for field in result["recipe"].values():
            self.assertEqual(field["status"], "missing")
            self.assertNotIn("value", field)

    def test_unknowns_custom_wb_and_legacy_dr(self):
        result = fixture("synthetic-color-and-unknown")
        r = result["recipe"]
        self.assertEqual(r["film_simulation"]["value"], "reala_ace")
        self.assertEqual(r["color"]["value"], -4)
        self.assertEqual(r["grain_size"]["status"], "missing")
        self.assertEqual(r["color_chrome_effect"]["raw_value"], 12345)
        self.assertEqual(r["white_balance"]["value"], "custom_3")
        self.assertIn("portability", r["white_balance"])
        self.assertEqual(r["dynamic_range"]["status"], "unresolved")
        self.assertEqual(r["dynamic_range"]["published_label"], "Wide1 (230%)")
        rendered = json.dumps(result)
        self.assertNotIn("PRIVATE-SERIAL", rendered)
        self.assertNotIn("PRIVATE-OWNER", rendered)
        self.assertIn("0x7ffe", rendered)

    def test_wb_policy_is_explicit_and_never_truncates(self):
        raw = [(0x100A, 9, [60, -40])]
        self.assertEqual(parse_jpeg(make_jpeg(raw))["recipe"]["white_balance_shift"]["status"], "unresolved")
        field = parse_jpeg(make_jpeg(raw), wb_shift_scale="heuristic")["recipe"]["white_balance_shift"]
        self.assertEqual(field["value"], {"red": 3, "blue": -2})
        self.assertEqual(field["basis"], "explicit_heuristic")
        for pair in ([9, 180], [21, 0], [200, 0], [-181, 0]):
            with self.subTest(pair=pair):
                r = parse_jpeg(make_jpeg([(0x100A, 9, pair)]), wb_shift_scale="heuristic")
                self.assertEqual(r["recipe"]["white_balance_shift"]["status"], "unresolved")

    def test_duplicate_and_wrong_type_cannot_become_known(self):
        for tags in ([(0x1001, 3, 3), (0x1001, 3, 5)], [(0x1001, 2, b"SECRET\0")],
                     [(0x1001, 3, [3, 5])]):
            r = parse_jpeg(make_jpeg(tags))
            self.assertIn(r["recipe"]["sharpness"]["status"], ("ambiguous", "malformed"))
            self.assertNotIn("SECRET", json.dumps(r))

    def test_color_and_film_uncertainty(self):
        r = parse_jpeg(make_jpeg([(0x1401, 3, 0)]))["recipe"]
        self.assertEqual(r["film_simulation"]["status"], "unresolved")
        self.assertEqual(r["film_simulation"]["candidate"], "provia")
        r = parse_jpeg(make_jpeg([(0x1401, 3, 65535), (0x1003, 3, 0)]))["recipe"]
        self.assertEqual(r["film_simulation"]["raw_value"], 65535)

    def test_manual_missing_priority_unknown_not_guessed(self):
        for tags, field in (([(0x1402, 3, 1)], "dynamic_range"),
                            ([(0x1443, 3, 1)], "d_range_priority"),
                            ([(0x1402, 3, 1), (0x1403, 3, 800)], "dynamic_range")):
            result = parse_jpeg(make_jpeg(tags))["recipe"][field]
            self.assertEqual(result["status"], "unresolved")
            self.assertNotIn("value", result)

    def test_ifd_offset_cannot_escape_app1(self):
        for order in ("<", ">"):
            with self.subTest(order=order):
                original = make_jpeg([], order=order)
                self.assertEqual(parse_jpeg(original)["status"], "ok")
                # An empty, complete IFD exists in a later APP2 payload. The
                # IFD0 pointer must still be bounded to EXIF's APP1 region.
                outside_ifd = len(original) - 2 + 4
                empty_ifd = struct.pack(order + "HI", 0, 0)
                data = bytearray(original[:-2] + b"\xff\xe2" +
                                 struct.pack(">H", len(empty_ifd) + 2) + empty_ifd + original[-2:])
                layout = SyntheticExifLayout(data)
                self.assertGreater(outside_ifd, layout.app1_end)
                self.assertEqual(data[outside_ifd:outside_ifd + 6], empty_ifd)
                struct.pack_into(order + "I", data, layout.tiff_start + 4,
                                 outside_ifd - layout.tiff_start)
                self.assertEqual(layout.unpack("H", layout.tiff_start + 2), 42)
                self.assertEqual(layout.unpack("I", layout.tiff_start + 4),
                                 outside_ifd - layout.tiff_start)
                result = parse_jpeg(bytes(data))
                self.assertEqual(result["status"], "malformed_exif")
                self.assertEqual(result["issues"],
                                 ["value or directory exceeds its enclosing metadata region"])

    def test_maker_value_cannot_escape_declared_maker_note(self):
        for order in ("<", ">"):
            with self.subTest(order=order):
                data = bytearray(make_jpeg([(0x100A, 9, [20, 40])], order=order))
                control = parse_jpeg(bytes(data), wb_shift_scale="times20")
                self.assertEqual(control["status"], "ok")
                self.assertEqual(control["recipe"]["white_balance_shift"]["value"],
                                 {"red": 1, "blue": 2})
                layout = SyntheticExifLayout(data)
                entry = layout.exif_entry(0x927C)
                self.assertEqual(layout.unpack("H", entry + 2), 7)
                note_count = layout.unpack("I", entry + 4)
                note_start = layout.tiff_start + layout.unpack("I", entry + 8)
                self.assertEqual(data[note_start:note_start + 8], b"FUJIFILM")
                note_ifd = struct.unpack_from("<I", data, note_start + 8)[0]
                self.assertEqual(struct.unpack_from("<H", data, note_start + note_ifd)[0], 1)
                wb_entry = note_start + note_ifd + 2
                self.assertEqual(struct.unpack_from("<HHI", data, wb_entry), (0x100A, 9, 2))
                payload_offset = struct.unpack_from("<I", data, wb_entry + 8)[0]
                payload_start = note_start + payload_offset
                payload = bytes(data[payload_start:payload_start + 8])
                self.assertEqual(struct.unpack("<ii", payload), (20, 40))
                self.assertLessEqual(payload_start + 8, layout.app1_end)
                self.assertLess(payload_offset, note_count)
                # Shorten only MakerNote's declared extent. The entire WB
                # payload remains physically present inside EXIF APP1.
                struct.pack_into(order + "I", data, entry + 4, payload_offset)
                self.assertEqual(layout.unpack("I", entry + 4), payload_offset)
                self.assertEqual(data[payload_start:payload_start + 8], payload)
                result = parse_jpeg(bytes(data), wb_shift_scale="times20")
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["recipe"]["white_balance_shift"]["status"], "malformed")
                self.assertEqual(raw_tag(result, "FujiFilm", "0x100a")["status"], "out_of_bounds")
                self.assertEqual(result["input"]["maker_note_bytes"], payload_offset)

    def test_truncated_file_does_not_supply_partial_app1(self):
        data = make_jpeg([(0x100A, 9, [20, 40])])
        self.assertEqual(parse_jpeg(data)["status"], "ok")
        layout = SyntheticExifLayout(data)
        result = parse_jpeg(data[:layout.app1_end - 1])
        self.assertEqual(result["status"], "invalid_jpeg")
        self.assertEqual(result["issues"], ["truncated or invalid JPEG segment"])
        self.assertEqual(result["recipe"]["white_balance_shift"]["status"], "missing")

    def test_duplicate_app1_is_ambiguous(self):
        data = make_jpeg([])
        self.assertEqual(parse_jpeg(data)["status"], "ok")
        result = parse_jpeg(data[:-2] + data[2:])
        self.assertEqual(result["status"], "malformed_exif")
        self.assertEqual(result["issues"], ["multiple EXIF APP1 segments are ambiguous"])

    def test_cyclic_exif_pointer_is_rejected(self):
        for order in ("<", ">"):
            with self.subTest(order=order):
                data = bytearray(make_jpeg([], order=order))
                self.assertEqual(parse_jpeg(bytes(data))["status"], "ok")
                layout = SyntheticExifLayout(data)
                pointer = layout.entry(layout.root, 0x8769)
                self.assertEqual(struct.unpack_from(order + "HHI", data, pointer), (0x8769, 4, 1))
                struct.pack_into(order + "I", data, pointer + 8, layout.root)
                self.assertEqual(struct.unpack_from(order + "HHI", data, pointer), (0x8769, 4, 1))
                self.assertEqual(layout.unpack("I", pointer + 8), layout.root)
                result = parse_jpeg(bytes(data))
                self.assertEqual(result["status"], "malformed_exif")
                self.assertEqual(result["issues"], ["invalid or cyclic ExifIFD pointer"])

    def test_tiff_count_and_signature_limits(self):
        data = bytearray(make_jpeg([]))
        start = data.rindex(b"FUJIFILM")
        struct.pack_into("<H", data, start + 12, 65535)
        self.assertEqual(parse_jpeg(bytes(data))["status"], "malformed_exif")
        self.assertEqual(parse_jpeg(make_jpeg([]).replace(b"FUJIFILM", b"OTHERXXX"))["status"], "no_fujifilm_makernote")

    def test_all_truncation_boundaries_and_deterministic_garbage(self):
        data = (FIXTURES / "synthetic-le-acros-red.jpg").read_bytes()
        for length in range(len(data)):
            result = parse_jpeg(data[:length])
            json.dumps(result, allow_nan=False)
            self.assertIn(result["status"], ("invalid_jpeg", "partial", "no_exif", "malformed_exif"))
        rng = random.Random(14319)
        for unused in range(100):
            data = rng.randbytes(rng.randrange(200))
            json.dumps(parse_jpeg(data), allow_nan=False)

    def test_xmp_and_complete_metadata_with_incomplete_image(self):
        xmp = b"http://ns.adobe.com/xap/1.0/\0<example/>"
        segment = b"\xff\xe1" + struct.pack(">H", len(xmp) + 2) + xmp
        data = make_jpeg([(0x1001, 3, 3)])
        result = parse_jpeg(data[:2] + segment + data[2:-2])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["recipe"]["sharpness"]["value"], 0)

    def test_color_space_conflicts(self):
        result = parse_jpeg(make_jpeg([], color_space=1, interop=b"R03\0"))
        self.assertEqual(result["observations"]["color_space"]["status"], "ambiguous")

    def test_color_space_array_remains_unresolved(self):
        for order in ("<", ">"):
            with self.subTest(order=order):
                malformed = bytearray(make_jpeg([], order=order, color_space=65535, interop=b"R03\0"))
                control = parse_jpeg(bytes(malformed))
                self.assertEqual(control["observations"]["color_space"]["value"], "adobe_rgb")
                layout = SyntheticExifLayout(malformed)
                entry = layout.exif_entry(0xA001)
                self.assertEqual(struct.unpack_from(order + "HHI", malformed, entry), (0xA001, 3, 1))
                # Preserve SHORT and the valid InteropIndex; only change the
                # scalar count into an invalid two-value inline array.
                struct.pack_into(order + "I", malformed, entry + 4, 2)
                self.assertEqual(struct.unpack_from(order + "HHI", malformed, entry), (0xA001, 3, 2))
                result = parse_jpeg(bytes(malformed))
                self.assertEqual(result["observations"]["interop_index"]["value"], "R03")
                self.assertEqual(result["observations"]["exif_color_space"]["status"], "malformed")
                self.assertEqual(result["observations"]["color_space"]["status"], "unresolved")
                self.assertEqual(result["observations"]["color_space"]["reason"], "malformed color-space metadata")
                self.assertEqual(raw_tag(result, "ExifIFD", "0xa001")["value"], [65535, 0])

    def test_conformance_extractor_and_json_round_trip(self):
        document = json.loads((ROOT / "fixtures/conformance/jpeg-extractor.json").read_text())
        self.assertEqual(document["schema_version"], 1)
        self.assertFalse(document["provenance"]["hardware_evidence"])
        for case in document["cases"]:
            # Each case passes its WB shift scale to the extractor explicitly.
            self.assertEqual(set(case["coverage"]["reference"]),
                             {"fixture_integrity", "jpeg_extractor", "extractor_json_round_trip"})
            tags = [(int(tag["tag"], 16), tag["type"],
                     tag["value"].encode("ascii") if tag["type"] == 2 else tag["value"])
                    for tag in case["input"]["tags"]]
            for order in ("<", ">"):
                with self.subTest(case=case["id"], order=order):
                    model = (case["input"].get("model", "SYNTHETIC FIXTURE") + "\0").encode("ascii")
                    result = parse_jpeg(make_jpeg(tags, order=order, model=model),
                                        **case["input"]["extractor"])
                    self.assertEqual(result["status"], "ok")
                    for expectation in case["expected"]["extractor"]:
                        self.assertEqual(at_path(result, expectation["path"]), expectation["equals"],
                                         expectation["path"])
                    for path in case["expected"].get("absent", []):
                        self.assertNotIn(path[-1], at_path(result, path[:-1]))
                    serialized = json.dumps(result, allow_nan=False)
                    for sentinel in case["expected"].get("excluded_text", []):
                        self.assertNotIn(sentinel, serialized)
                    # Test the actual extractor document, including mapping
                    # source, raw observations, applicability and uncertainty.
                    restored = json.loads(serialized)
                    self.assertEqual(restored, result)
                    self.assertFalse(restored["input"]["pixels_validated"])
                    for expectation in case["expected"]["extractor"]:
                        self.assertEqual(at_path(restored, expectation["path"]), expectation["equals"])

    def test_sanitized_capture_values_and_provenance(self):
        manifest = json.loads((FIXTURES / "capture-derived-manifest.json").read_text())
        # Expected semantic settings independently follow the selected ExifTool
        # readings and the public captures' editor walk, not parser-generated JSON.
        expected = {1133: ("provia", -4, 3, 100, "off", "adobe_rgb"),
                    1753: ("classic_chrome", -2, 0, 100, "on", "srgb"),
                    215: ("astia", -4, 0, 100, "on", "srgb"),
                    546: ("classic_chrome", -2, 2, 400, "off", "adobe_rgb")}
        for case in manifest["cases"]:
            with self.subTest(tid=case["get_object_tid"]):
                data = (FIXTURES / case["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), case["sha256"])
                self.assertFalse(case["transfer_complete"])
                self.assertTrue(case["exif_app1_complete"])
                result = parse_jpeg(data)
                r, o = result["recipe"], result["observations"]
                values = (r["film_simulation"]["value"], r["sharpness"]["value"], r["color"]["value"],
                          r["dynamic_range"]["value"]["percent"], o["lens_modulation_optimizer"]["value"],
                          o["color_space"]["value"])
                self.assertEqual(values, expected[case["get_object_tid"]])
                self.assertEqual(r["white_balance_shift"]["status"], "unresolved")
                self.assertTrue(all(e["name"] != "unexported" or
                                    (e["group"], e["tag"]) in (("IFD0", "0x8769"), ("ExifIFD", "0x927c"), ("ExifIFD", "0xa005"))
                                    for e in result["raw_tags"]))

    def test_fixture_hashes_and_cli(self):
        manifest = json.loads((FIXTURES / "synthetic-manifest.json").read_text())
        for item in manifest["files"]:
            self.assertEqual(hashlib.sha256((FIXTURES / item["path"]).read_bytes()).hexdigest(), item["sha256"])
        run = subprocess.run([sys.executable, str(ROOT / "tools/jpeg_recipe.py"),
                              str(FIXTURES / "synthetic-le-acros-red.jpg")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(json.loads(run.stdout)["recipe"]["film_simulation"]["value"], "acros_red")

    @unittest.skipUnless(shutil.which("exiftool"), "independent ExifTool executable is optional")
    def test_against_pinned_exiftool_golden_values(self):
        golden = json.loads((FIXTURES / "exiftool-13.55-expected.json").read_text())
        version = subprocess.check_output(["exiftool", "-ver"], text=True).strip()
        if version != "13.55":
            self.skipTest("golden oracle pins ExifTool 13.55; installed version is " + version)
        for case in golden["cases"]:
            with self.subTest(path=case["path"]):
                tags = ["-" + key for key in case["expected"]]
                command = ["exiftool", "-j", "-s", *tags, str(FIXTURES / case["path"])]
                actual = json.loads(subprocess.check_output(command, text=True))[0]
                actual.pop("SourceFile", None)
                self.assertEqual(actual, case["expected"])
        capture = json.loads((FIXTURES / "capture-derived-manifest.json").read_text())
        for case in capture["cases"]:
            with self.subTest(path=case["path"]):
                def group(name):
                    return ("IFD0" if name in ("Make", "Model") else "ExifIFD" if name == "ColorSpace"
                            else "InteropIFD" if name == "InteropIndex" else "FujiFilm")
                command = ["exiftool", "-j", "-s", *["-" + group(key) + ":" + key for key in case["expected"]],
                           str(FIXTURES / case["path"])]
                actual = json.loads(subprocess.check_output(command, text=True))[0]
                actual.pop("SourceFile", None)
                self.assertEqual(actual, case["expected"])


if __name__ == "__main__":
    unittest.main()
