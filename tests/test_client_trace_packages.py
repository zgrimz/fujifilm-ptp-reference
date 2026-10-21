# SPDX-License-Identifier: MIT
"""Integrity and disclosure checks for the 29 X-T50 client-trace packages, and the write-timing figures the record cites."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "evidence" / "xt50-client-traces"
SPEC = importlib.util.spec_from_file_location("client_trace_export", SERIES / "export.py")
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)
sys.path.insert(0, str(ROOT / "tools"))
import write_timing  # noqa: E402

PRIVATE_KEYS = {"serial", "serialHash", "deviceIdentifier", "connectionID", "sessionID", "resultID", "runID", "evidenceID",
                "name", "nameBefore", "nameApplied", "recipeName", "currentName", "expectedName", "originalName",
                "usbVendorID", "usbProductID"}
UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")


def keys_of(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_of(item)


def ledger(evidence_id):
    return [json.loads(line) for line in (SERIES / evidence_id / "transactions.jsonl").read_text().splitlines()]


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClientTracePackageTests(unittest.TestCase):
    def test_every_package_matches_its_inventory_entry_and_exporter(self):
        inventory = json.loads((ROOT / "evidence" / "xt50-client-traces-sources.json").read_text())
        sources = {inventory["directory"] + "/" + item["path"]: item for item in inventory["artifacts"]}
        self.assertEqual(len(EXPORT.SPECS), 29)
        self.assertEqual(sorted(path.name for path in SERIES.iterdir() if path.is_dir()), sorted(EXPORT.SPECS))
        for evidence_id, (source_sha, file_name, count) in EXPORT.SPECS.items():
            with self.subTest(package=evidence_id):
                manifest = json.loads((SERIES / evidence_id / "manifest.json").read_text())
                source = sources[manifest["source"]["archivePath"]]
                self.assertEqual(manifest["source"]["archivePath"], EXPORT.DIRECTORY + "/" + file_name)
                self.assertEqual((manifest["source"]["sha256"], manifest["source"]["bytes"], manifest["source"]["revision"]),
                                 (source["sha256"], source["bytes"], inventory["revision"]))
                self.assertEqual((source_sha, manifest["coverage"]["sourceEntries"]), (source["sha256"], count))
                for name, metadata in manifest["artifacts"].items():
                    content = (SERIES / evidence_id / name).read_bytes()
                    self.assertEqual((len(content), hashlib.sha256(content).hexdigest()), (metadata["bytes"], metadata["sha256"]))
                for file_key, hash_key in (("generator", "generatorSha256"), ("ledgerModule", "ledgerModuleSha256"),
                                           ("observationModule", "observationModuleSha256"), ("helperModule", "helperModuleSha256")):
                    self.assertEqual(file_hash(SERIES / evidence_id / manifest["transform"][file_key]), manifest["transform"][hash_key])

    def test_full_order_and_payload_allowlist(self):
        for evidence_id, (_, _, count) in EXPORT.SPECS.items():
            with self.subTest(package=evidence_id):
                rows = ledger(evidence_id)
                self.assertEqual([row["sourceIndex"] for row in rows], list(range(count)))
                self.assertEqual([row["sequence"] for row in rows], list(range(1, count + 1)))
                for row in rows:
                    for key in ("dataInLE", "dataOutLE"):
                        if key in row:
                            self.assertIn(row["parameters"][0], EXPORT.SCALAR_CODES)
                            self.assertLessEqual(len(bytes.fromhex(row[key])), 4)
                    for key in ("emptyNameInHex", "emptyNameOutHex"):
                        if key in row:
                            self.assertEqual(row["parameters"], [0xD18D])
                            self.assertIn(row[key], EXPORT.EMPTY_NAME_PAYLOADS)
                    if row["opcode"] not in ("0x1014", "0x1015", "0x1016"):
                        self.assertNotIn("parameters", row)

    def test_no_private_keys_identifiers_or_long_hex(self):
        for evidence_id in EXPORT.SPECS:
            for name in ("transactions.jsonl", "findings.json", "manifest.json"):
                with self.subTest(package=evidence_id, artifact=name):
                    text = (SERIES / evidence_id / name).read_text()
                    values = [json.loads(line) for line in text.splitlines()] if name.endswith(".jsonl") else [json.loads(text)]
                    self.assertFalse(PRIVATE_KEYS & {key for value in values for key in keys_of(value)})
                    self.assertIsNone(UUID.search(text))
                    self.assertIsNone(re.search(r"(?:iPad|iPhone)[0-9]+,[0-9]+", text))
                    long_runs = {len(run) for run in re.findall(r"[0-9A-Fa-f]{20,}", text)}
                    self.assertTrue(long_runs <= ({40, 64} if name == "manifest.json" else set()))

    def test_private_strings_cover_every_kind_of_private_field(self):
        name, recipe, uuid = "Night Walk", "Test Recipe", "0E8EC0D1-0000-4FA0-8D6A-000000000000"
        original = {
            "camera": {"serialHash": "0123456789abcdef", "productName": "X-T50"}, "host": {"deviceIdentifier": "Device0,0"},
            "connectionID": uuid, "notes": ["C7: a free-text note naming Night Walk"],
            "slots": {"reads": [{"name": name, "properties": [{"code": "0xD18E", "name": "Image Size", "value": "0700"}]}]},
            "guidedTests": [{"kitchenObservations": {uuid: "yes"},
                             "writePass": {"trials": [{"recipeName": recipe, "menuComparison": {"name": "Morning"}}],
                                           "restores": [{"verification": {"currentName": "Evening Light"}}]}}],
            "pushes": [{"fields": [{"code": "0xD192", "name": "Film Simulation"}], "nameBefore": "Old Name"}],
            "transactions": [{"operation": "0x1016", "parameters": ["0xD18D"], "outData": "0A4E0069006700"},
                             {"operation": "0x900C", "parameters": [], "outData": "4400530043004600…(+66 bytes)"}],
        }
        secrets = EXPORT.private_strings(original)
        for leaked in (name, name.encode("utf-16-le").hex(), recipe, "Morning", "Evening Light", "Old Name", uuid.lower(),
                       "0123456789abcdef", "Device0,0", "0a4e0069006700", "4400530043004600"):
            self.assertIn(leaked.lower(), secrets)
        for label in ("image size", "film simulation", "x-t50"):
            self.assertNotIn(label, secrets)
        with self.assertRaises(ValueError):
            EXPORT.owner_report_package.check_disclosure({"x.json": json.dumps({"v": name}).encode()}, secrets)

    def test_keyed_identifier_only_where_the_report_is_keyed(self):
        keyed = {"xt50-20261015-172015", "xt50-20261017-175208", "xt50-20261018-173731", "xt50-20261018-174411",
                 "xt50-20261019-101935", "xt50-20261019-102134", "xt50-20261019-125007", "xt50-20261019-140542"}
        manifests = {path.parent.name: json.loads(path.read_text()) for path in (ROOT / "evidence").rglob("manifest.json")}
        values = set()
        for evidence_id, manifest in manifests.items():
            with self.subTest(package=evidence_id):
                identifier = manifest["camera"].get("identifier")
                if evidence_id in keyed:
                    self.assertEqual(identifier["scheme"], "hmac-sha256")
                    self.assertRegex(identifier["value"], r"\A[0-9a-f]{16}\Z")
                    values.add(identifier["value"])
                else:
                    self.assertIsNone(identifier, "only a keyed identifier is ever published")
        self.assertEqual(len(values), 1, "one body through one phone")
        self.assertEqual(sum(evidence_id in EXPORT.SPECS for evidence_id in keyed), 6)

    def test_an_unkeyed_hash_is_never_returned(self):
        keyed_identifier = EXPORT.client_report_package.keyed_identifier
        self.assertIsNone(keyed_identifier({"serialHash": "0123456789abcdef"}))
        self.assertIsNone(keyed_identifier({"serialHash": "0123456789abcdef", "serialHashScheme": "sha256"}))
        self.assertEqual(keyed_identifier({"serialHash": "0123456789abcdef", "serialHashScheme": "hmac-sha256"})["value"],
                         "0123456789abcdef")
        for bad in ("0123456789ABCDEF", "0123456789abcde", "", None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                keyed_identifier({"serialHash": bad, "serialHashScheme": "hmac-sha256"})

    def test_wrong_hash_and_checkout_original_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            EXPORT.build_package(b"{}", "xt50-20260906-180652", EXPORT.__file__)
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            EXPORT.main([__file__, "--check"])
        self.assertIn("keep the original outside the repository", error.getvalue())


class WriteTimingTests(unittest.TestCase):
    """The figures docs/01-transport.md and evidence/write-timing.md cite, recomputed from the public ledgers."""

    @classmethod
    def setUpClass(cls):
        cls.figures = write_timing.timing()

    def band(self, figure):
        fast, slow = figure["fast"], figure["slow"]
        return (figure["count"], fast["count"], fast["minimum"], fast["maximum"], fast["median"],
                (slow["count"], slow["minimum"], slow["maximum"]) if slow else None)

    def test_traces_counted(self):
        self.assertEqual(len(self.figures["X-T50"]["traces"]), 31)
        self.assertEqual(len(self.figures["GFX100S"]["traces"]), 9)
        self.assertNotIn("gfx100s-20260917-211657", self.figures["GFX100S"]["traces"], "a prefix of the 21:51 trace")

    def test_x_t50_figures(self):
        figures = self.figures["X-T50"]
        self.assertEqual(self.band(figures["nameWrites"]), (47, 41, 76, 114, 102, (6, 266, 275)))
        self.assertEqual(self.band(figures["bankSettingWrites"]), (922, 882, 97, 160, 118, (40, 288, 318)))
        self.assertEqual(self.band(figures["whiteBalanceWrites"]), (47, 43, 102, 145, 129, (4, 291, 300)))
        self.assertEqual(self.band(figures["liveImageSizeWrites"]), (40, 40, 29, 49, 34, None))
        self.assertEqual(figures["propertyReads"], {"count": 8149, "maximum": 60, "atOrAbove100Ms": 0})

    def test_gfx100s_figures(self):
        figures = self.figures["GFX100S"]
        self.assertEqual(self.band(figures["nameWrites"]), (4, 2, 103, 103, 103, (2, 325, 329)))
        self.assertEqual(self.band(figures["bankSettingWrites"]), (81, 76, 67, 135, 118, (5, 344, 356)))
        self.assertEqual(self.band(figures["whiteBalanceWrites"]), (4, 4, 78, 120, 118, None))
        self.assertIsNone(figures["liveImageSizeWrites"])
        self.assertEqual(figures["propertyReads"], {"count": 1556, "maximum": 90, "atOrAbove100Ms": 0})

    def test_no_write_falls_near_the_slow_boundary(self):
        durations = [row["durationMs"] for _, _, rows in write_timing.traces() for row in rows
                     if row["opcode"] == "0x1016" and row["response"] == "0x2001"
                     and row.get("parameters", [None])[0] in [write_timing.NAME, *write_timing.BANK_SETTINGS]]
        self.assertEqual([value for value in durations if 161 <= value <= 265], [])

    def test_empty_name_writes_are_fast(self):
        empty = [row["durationMs"] for _, _, rows in write_timing.traces() for row in rows if "emptyNameOutHex" in row]
        self.assertEqual(sorted(empty), [76, 100])


if __name__ == "__main__":
    unittest.main()
