# SPDX-License-Identifier: MIT
"""Integrity and disclosure checks for the ten sanitized GFX100S owner-report packages and the X-T20 owner-log package."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OWNER = load("owner_report_package", EVIDENCE / "owner_report_package.py")
XT20_RUN = "xt20-undated-172851"
XT20 = load("xt20_export", EVIDENCE / XT20_RUN / "export.py")
GFX_RUNS = {"gfx100s-20260915-181130": 114, "gfx100s-20260915-194552": 244, "gfx100s-20260915-195437": 237,
            "gfx100s-20260917-211657": 171, "gfx100s-20260917-215104": 384, "gfx100s-20260929-221826": 165,
            "gfx100s-20260929-222001": 167, "gfx100s-20260929-225137": 165, "gfx100s-20260929-231523": 165,
            "gfx100s-20260929-231728": 167}
LATE_SEPTEMBER = [run for run in GFX_RUNS if run.startswith("gfx100s-20260929")]
# Keys under which the originals hold private values. None may appear anywhere in a published artifact.
PRIVATE_KEYS = {"serial", "serialHash", "serialNumber", "deviceIdentifier", "sessionID", "name", "nameBefore", "nameApplied",
                "recipeName", "productName", "appShowedProductName", "usbVendorID", "usbProductID", "activity"}
UUID = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")
# The one long hexadecimal run a GFX100S artifact may hold outside its manifest: the profile's first 64 bytes, which are
# its cell count, its IOPCode FF149502 in UCS-2, and zero padding.
PROFILE_HEAD = "1c000846004600310034003900350030003200" + "0" * 90


def keys_of(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_of(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_of(item)


def ledger(run, name="transactions.jsonl"):
    return [json.loads(line) for line in (EVIDENCE / run / name).read_text().splitlines()]


def artifact(run, name):
    return json.loads((EVIDENCE / run / name).read_text())


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GFX100SPackageTests(unittest.TestCase):
    def test_source_generator_and_data_integrity(self):
        inventory = json.loads((EVIDENCE / "gfx100s-september-sources.json").read_text())
        sources = {inventory["directory"] + "/" + item["path"]: item for item in inventory["artifacts"]}
        for run, count in GFX_RUNS.items():
            with self.subTest(run=run):
                manifest = artifact(run, "manifest.json")
                source = sources[manifest["source"]["archivePath"]]
                self.assertEqual((manifest["source"]["sha256"], manifest["source"]["bytes"], manifest["source"]["revision"]),
                                 (source["sha256"], source["bytes"], inventory["revision"]))
                self.assertEqual(manifest["coverage"]["sourceEntries"], count)
                for name, metadata in manifest["artifacts"].items():
                    content = (EVIDENCE / run / name).read_bytes()
                    self.assertEqual((len(content), hashlib.sha256(content).hexdigest()), (metadata["bytes"], metadata["sha256"]))
                for file_key, hash_key in (("generator", "generatorSha256"), ("sharedGenerator", "sharedGeneratorSha256"),
                                           ("ledgerModule", "ledgerModuleSha256"), ("helperModule", "helperModuleSha256")):
                    self.assertEqual(file_hash(EVIDENCE / run / manifest["transform"][file_key]), manifest["transform"][hash_key])
                spec = load(run.replace("-", "_"), EVIDENCE / run / "export.py").SPEC
                self.assertEqual((spec["evidenceId"], spec["sourceSha256"], spec["sourcePath"], spec["sourceRevision"]),
                                 (run, source["sha256"], manifest["source"]["archivePath"], inventory["revision"]))

    def test_full_order_and_payload_allowlist(self):
        for run, count in GFX_RUNS.items():
            with self.subTest(run=run):
                rows = ledger(run)
                self.assertEqual([row["sourceIndex"] for row in rows], list(range(count)))
                self.assertEqual([row["sequence"] for row in rows], list(range(1, count + 1)))
                for row in rows:
                    for key in ("dataInLE", "dataOutLE"):
                        if key in row:
                            self.assertIn(row["parameters"][0], OWNER.SCALAR_CODES)
                            self.assertLessEqual(len(bytes.fromhex(row[key])), 4)
                    for key in ("emptyNameInHex", "emptyNameOutHex"):
                        if key in row:
                            self.assertEqual(row["parameters"], [0xD18D])
                            self.assertIn(row[key], OWNER.EMPTY_NAME_PAYLOADS)
                    if row["opcode"] not in ("0x1014", "0x1015", "0x1016"):
                        self.assertNotIn("parameters", row)
                manifest = artifact(run, "manifest.json")
                self.assertIsNone(manifest["camera"]["usbMode"])
                self.assertEqual(manifest["camera"]["provenance"], "owner_report")
                self.assertEqual(manifest["conditions"]["autoUpdateCustomSetting"], "unknown")
                self.assertEqual(manifest["time"]["connectionIds"], "omitted")

    def test_no_private_keys_identifiers_or_unexpected_hex(self):
        for run in GFX_RUNS:
            for name in ("transactions.jsonl", "client-records.json", "findings.json", "manifest.json"):
                with self.subTest(run=run, artifact=name):
                    text = (EVIDENCE / run / name).read_text()
                    values = ledger(run, name) if name.endswith(".jsonl") else [json.loads(text)]
                    self.assertFalse(PRIVATE_KEYS & {key for value in values for key in keys_of(value)})
                    self.assertIsNone(UUID.search(text))
                    self.assertIsNone(re.search(r"(?:iPad|iPhone)[0-9]+,[0-9]+", text), "a host device model identifier")
                    if name != "manifest.json":
                        self.assertTrue(all(found == PROFILE_HEAD for found in re.findall(r"[0-9A-Fa-f]{20,}", text)))

    def test_the_two_september_17_exports_share_their_first_rows(self):
        earlier, later = ledger("gfx100s-20260917-211657"), ledger("gfx100s-20260917-215104")
        self.assertEqual(later[:len(earlier)], earlier)

    def test_reviewed_findings(self):
        before = artifact("gfx100s-20260915-181130", "findings.json")["reviewed"]
        self.assertEqual((before["firmwareReported"], before["selectorWithoutAnyWrite"]["valueUnsigned"],
                          before["imageSizeAtThatSelector"]["valueUnsigned"]), ("1.32", 7, 16))
        probe = artifact("gfx100s-20260915-194552", "findings.json")["reviewed"]["grainProbe"]
        self.assertEqual([(step["writtenUnsigned"], step["response"], step["readbackUnsigned"]) for step in probe["steps"]],
                         [(0, "0x201C", 3), (2, "0x2001", 2), (1, "0x2001", 6), (3, "0x2001", 3), (6, "0x201C", 3),
                          (4, "0x2001", 4), (7, "0x201C", 4), (5, "0x2001", 5), (1, "0x2001", 7), (8, "0x201C", 7)])
        write_pass = artifact("gfx100s-20260915-195437", "findings.json")["reviewed"]
        restore = write_pass["restoreOfC2"]
        self.assertEqual((restore["nameWrite"]["sequence"], restore["nameWrite"]["durationMs"]), (192, 325))
        self.assertEqual(restore["writes"][-1], {"sequence": 213, "property": "0xD1A5", "writtenUnsigned": 14,
                                                 "response": "0x201C", "durationMs": 6})
        self.assertEqual(restore["liveD1A5BeforeUnsigned"], 14)
        self.assertEqual(write_pass["trialOnC2AfterPowerCycle"]["toningUnsigned"], {"0xD193": 20, "0xD194": 65526})
        self.assertEqual({key: write_pass["grainRollback"][key] for key in ("savedUnsigned", "trialUnsigned",
                                                                            "restoreWroteUnsigned", "readbackUnsigned")},
                         {"savedUnsigned": 6, "trialUnsigned": 5, "restoreWroteUnsigned": 1, "readbackUnsigned": 7})
        for run in ("gfx100s-20260917-211657", "gfx100s-20260917-215104"):
            upload = artifact(run, "findings.json")["reviewed"]["conversion"]
            self.assertEqual((upload["handlesBeforeUpload"]["handleCount"], upload["sendObject"]["bytesSent"],
                              upload["sendObject"]["durationMs"], upload["handlesAfterUpload"]["handleCount"],
                              upload["profileAfterUpload"]["bytes"], upload["clientProfileHarvest"]["iopCode"],
                              upload["clientProfileHarvest"]["first64BytesHex"]),
                             (0, 208071296, 5392, 0, 621, "FF149502", PROFILE_HEAD))
        dr = artifact("gfx100s-20260917-215104", "findings.json")["reviewed"]["dynamicRange400"]
        self.assertEqual((dr["accepted"]["bank"], dr["accepted"]["readbackUnsigned"]), (2, 400))
        self.assertEqual([(entry["bank"], entry["response"], entry["readbackUnsigned"]) for entry in dr["refused"]],
                         [(3, "0x201C", 100), (4, "0x201C", 100)])
        for run in LATE_SEPTEMBER:
            with self.subTest(run=run):
                reviewed = artifact(run, "findings.json")["reviewed"]
                self.assertEqual(reviewed["dRangePriorityInTrace"]["c1Unsigned"], 0x8000)
                first = reviewed["dRangePriorityHistory"]["comparisons"][0]
                self.assertEqual((first["bank"], first["dRangePriority"]["clientShowed"],
                                  first["dRangePriority"]["ownerReportedCamera"]), (1, "Auto", "OFF"))

    def test_disclosure_check_catches_every_encoding(self):
        name, serial_hash, session = "Café Nuit", "ab" * 32, "00000000-1111-4222-8333-444444444444"
        original = {"camera": {"serialHash": serial_hash}, "host": {"deviceIdentifier": "Device0,0"},
                    "slots": {"reads": [{"name": name}]}, "pushes": [{"nameBefore": "Night"}],
                    "guidedTests": [{"sessionID": session}],
                    "transactions": [{"operation": "0x1015", "parameters": ["0xD18D"], "inData": "0A4300610066"},
                                     {"operation": "0x900C", "parameters": [], "outData": "4400530043004600…(+66 bytes)"}],
                    "propertySweep": {"entries": [{"code": "0xD18D", "value": "0441004200430000"}]}}
        secrets = OWNER.private_strings(original)
        for leaked in (name, name.encode("utf-16-le").hex().upper(), "Night", serial_hash.upper(), session.lower(),
                       "Device0,0", "0a4300610066", "4400530043004600", "0441004200430000"):
            with self.subTest(leaked=leaked), self.assertRaises(ValueError):
                OWNER.check_disclosure({"x.json": json.dumps({"value": leaked}).encode()}, secrets)
        with self.assertRaises(ValueError):
            OWNER.check_disclosure({"x.json": json.dumps({"value": name}, ensure_ascii=True).encode()}, secrets)
        OWNER.check_disclosure({"x.json": json.dumps({"value": "PROVIA / Standard"}).encode()}, secrets)

    def test_projection_fails_closed(self):
        sweep = OWNER.property_sweep({"slot": 1, "readOnly": False, "entries": [
            {"code": "0xD18D", "name": "Preset Name", "value": "0451005A0058000000"},
            {"code": "0xD18D", "value": "010000"}, {"code": "0xD190", "decoded": -1, "value": "FFFF"}]})
        self.assertNotIn("5a005800", json.dumps(sweep).lower())
        self.assertEqual([entry.get("valueOmitted") for entry in sweep["entries"]], [True, None, None])
        self.assertEqual((sweep["entries"][1]["emptyNameHex"], sweep["entries"][2]["valueUnsigned"]), ("010000", 65535))
        push = {"at": "2026-09-15T23:49:13Z", "slot": 2, "outcome": "applied", "firmwareVersion": "2.13", "modelID": "GFX100S",
                "nameWritten": True, "clampedFields": [], "fields": [], "nameBefore": "PRIVATE"}
        self.assertNotIn("PRIVATE", json.dumps(OWNER.push(push)))
        for bad in ({**push, "serialNumber": "PRIVATE"}, {**push, "modelID": "X-T50"}, {**push, "outcome": "PRIVATE"},
                    {**push, "fields": [{"code": "0xD18D", "outcome": "written", "wrote": "00", "isRecipeField": False}]}):
            with self.subTest(push=bad), self.assertRaises(ValueError):
                OWNER.push(bad)
        for bad in ("C1: PRIVATE note", "profile harvest: 621-byte profile, layout resolved at base 0x1FD and more"):
            with self.subTest(note=bad), self.assertRaises(ValueError):
                OWNER.note(bad)
        for bad in ("name@example.com", "line\nbreak", "x" * 49):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                OWNER.display(bad)
        with self.assertRaises(ValueError):
            OWNER.profile_header("0000  1C000846004600310034003900350030\n0020  " + "0" * 32)

    def test_wrong_hash_prevents_projection(self):
        def should_not_run(*_):
            self.fail("review ran before source verification")
        spec = {"evidenceId": "gfx100s-20260915-181130", "sourceSha256": "0" * 64, "sourceRevision": "0" * 40,
                "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-15/report.json", "transactionCount": 0}
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            OWNER.build_package(b"{}", spec, should_not_run, __file__)

    def test_original_inside_checkout_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            OWNER.package_main({}, lambda *_: None, __file__, [__file__, "--check"])
        self.assertIn("keep the original outside the repository", error.getvalue())


class XT20PackageTests(unittest.TestCase):
    def test_source_generator_and_data_integrity(self):
        inventory = json.loads((EVIDENCE / "xt20-sources.json").read_text())
        manifest = artifact(XT20_RUN, "manifest.json")
        source, = inventory["artifacts"]
        self.assertEqual((manifest["source"]["archivePath"], manifest["source"]["sha256"], manifest["source"]["bytes"],
                          manifest["source"]["revision"]),
                         (inventory["directory"] + "/" + source["path"], source["sha256"], source["bytes"], inventory["revision"]))
        self.assertEqual(XT20.SPEC["sourceSha256"], source["sha256"])
        for name, metadata in manifest["artifacts"].items():
            content = (EVIDENCE / XT20_RUN / name).read_bytes()
            self.assertEqual((len(content), hashlib.sha256(content).hexdigest()), (metadata["bytes"], metadata["sha256"]))
        for file_key, hash_key in (("generator", "generatorSha256"), ("helperModule", "helperModuleSha256")):
            self.assertEqual(file_hash(EVIDENCE / XT20_RUN / manifest["transform"][file_key]), manifest["transform"][hash_key])

    def test_every_line_kept_in_order_with_no_identifier(self):
        rows = ledger(XT20_RUN, "log.jsonl")
        self.assertEqual([row["sourceLine"] for row in rows], list(range(1, 151)))
        for name in ("log.jsonl", "findings.json"):
            with self.subTest(artifact=name):
                text = (EVIDENCE / XT20_RUN / name).read_text()
                values = ledger(XT20_RUN, name) if name.endswith(".jsonl") else [json.loads(text)]
                self.assertFalse(PRIVATE_KEYS & {key for value in values for key in keys_of(value)})
                self.assertIsNone(XT20.LONG_HEX.search(text))
                self.assertNotIn("04cb", text.lower())
                self.assertNotIn("02d4", text.lower())
                self.assertNotIn("serial", text.lower())

    def test_findings(self):
        findings = artifact(XT20_RUN, "findings.json")["findings"]
        self.assertEqual([connection["sessionOpenToDeviceInfoLogMs"] for connection in findings["connections"]], [1556, 9, 19, 9])
        self.assertEqual((findings["deviceInfo"]["datasetBytes"], len(findings["deviceInfo"]["operations"]),
                          len(findings["deviceInfo"]["properties"]), findings["deviceInfo"]["bankBlockAdvertised"]),
                         (595, 27, 168, False))
        report = findings["propertyReport"]
        self.assertEqual(report["bankBlock"], {"properties": 26, "valueResponse": "0x200A", "descriptorResponse": "0x200A"})
        self.assertEqual(report["d185"], {"property": "0xD185", "valueResponse": "0x2002", "descriptorResponse": "0x200A"})
        self.assertEqual(report["d183"]["descriptor"], {"enumeration": [0, 1], "dataType": "UINT16", "writable": True,
                                                        "factoryDefault": 65535, "current": 65535})

    def test_unreviewed_lines_stop_the_export(self):
        line = "17:28:51.375  [camera]  %s"
        self.assertEqual(XT20.log_rows(line % "Connect: hardware connect requested")[0]["event"], "connect_requested")
        device_info = 'DeviceInfo: FUJIFILM X-T20 fw 2.01 · PTP 100 · ext 0x00000006 "fujifilm.co.jp: 1.0; " · 595 bytes'
        self.assertEqual(XT20.log_rows(line % device_info)[0]["datasetBytes"], 595)
        for bad in (line % (device_info + " · serial 7AB12345"), line % "DeviceInfo: serial hash 0123456789abcdef",
                    "17:28:51.375  [camera]  Connect: hardware connect requested",
                    line % "Connect: hardware connect requested" + "\nSerial: 7AB12345",
                    "D18C  Slot Selector\n" + " " * 6 + "holds:   7AB12345"):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                XT20.log_rows(bad)

    def test_wrong_hash_and_checkout_original_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            XT20.build_package(b"17:28:51.375", XT20.SPEC, XT20.__file__)
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            XT20.main([__file__, "--check"])
        self.assertIn("keep the original outside the repository", error.getvalue())


if __name__ == "__main__":
    unittest.main()
