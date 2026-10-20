# SPDX-License-Identifier: MIT
"""Integrity and disclosure checks for the seven sanitized X-T50 bankprobe packages and the two client-report packages."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
SPEC = importlib.util.spec_from_file_location("bankprobe_package", EVIDENCE / "bankprobe_package.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
RUNS = {
    "20261015-232441": (1888, 1820, 68),
    "20261016-094028": (134, 124, 10),
    "20261016-095611": (221, 213, 8),
    "20261016-100752": (125, 121, 4),
    "20261019-102738": (39, 38, 1),
    "20261019-133848": (145, 142, 3),
}
INVENTORIES = {"20261019-102738": "xt50-20261019-sources.json",
               "20261019-133848": "xt50-20261019-133848-sources.json"}


def package(run):
    return EVIDENCE / ("xt50-" + run)


def rows(run):
    return [json.loads(line) for line in (package(run) / "transactions.jsonl").read_text().splitlines()]


class AdditionalEvidencePackageTests(unittest.TestCase):
    def test_source_and_generator_and_data_integrity(self):
        for run in RUNS:
            with self.subTest(run=run):
                inventory = json.loads((EVIDENCE / INVENTORIES.get(run, "xt50-october-sources.json")).read_text())
                sources = {item["path"]: item for item in inventory["artifacts"]}
                path = package(run)
                manifest = json.loads((path / "manifest.json").read_text())
                source = sources["logs/bankprobe-" + run + ".json"]
                self.assertEqual(manifest["source"]["sha256"], source["sha256"])
                self.assertEqual(manifest["source"]["archivePath"], inventory["directory"] + "/" + source["path"])
                self.assertEqual(manifest["source"]["revision"], inventory["revision"])
                for name, metadata in manifest["artifacts"].items():
                    content = (path / name).read_bytes()
                    self.assertEqual(len(content), metadata["bytes"])
                    self.assertEqual(hashlib.sha256(content).hexdigest(), metadata["sha256"])
                for file_key, hash_key in (("generator", "generatorSha256"), ("sharedGenerator", "sharedGeneratorSha256")):
                    self.assertEqual(hashlib.sha256((path / manifest["transform"][file_key]).read_bytes()).hexdigest(),
                                     manifest["transform"][hash_key])

    def test_full_row_order_and_missing_conditions_preserved(self):
        for run, (total, operations, events) in RUNS.items():
            with self.subTest(run=run):
                manifest = json.loads((package(run) / "manifest.json").read_text())
                ledger = rows(run)
                self.assertEqual([row["sourceIndex"] for row in ledger], list(range(total)))
                self.assertEqual(sum(row["kind"] == "transaction" for row in ledger), operations)
                self.assertEqual(sum(row["kind"] == "event" for row in ledger), events)
                self.assertIsNone(manifest["camera"]["usbMode"])
                self.assertEqual(manifest["conditions"]["autoUpdateCustomSetting"], "unknown")
                self.assertIsNone(manifest["time"]["timezone"])
                self.assertEqual(manifest["time"]["perTransactionTimestamps"], "absent")
                for row in ledger:
                    if row["kind"] == "transaction":
                        self.assertNotIn("recordedLocalTime", row)
                    for key in ("dataInLE", "dataOutLE"):
                        if key in row:
                            self.assertIn(row["parameters"][0], HELPER.SCALAR_CODES)
                            self.assertLessEqual(len(bytes.fromhex(row[key])), 4)
                    for key in ("emptyNameInHex", "emptyNameOutHex"):
                        if key in row:
                            self.assertEqual(row["parameters"], [0xD18D])
                            self.assertIn(row[key], HELPER.EMPTY_NAME_PAYLOADS)

    def test_only_the_two_empty_name_encodings_survive_on_d18d(self):
        rows_in = [{"op": "0x1015", "params": ["0xD18D"], "tid": i, "data_in": payload, "response": "0x2001"}
                   for i, payload in enumerate(("0f5200650067006700690065007300200050006f0072007400720061000000",
                                                "0100", "020000", "01000000", "00", "010000", "010000FF"))]
        rows_in.append({"op": "0x1016", "params": ["0xD18D"], "tid": 7, "data_out": "00", "response": "0x2001"})
        rows_in.append({"op": "0x1016", "params": ["0xD18D"], "tid": 8, "data_out": "010000", "response": "0x2001"})
        exported = HELPER.ledger_rows(rows_in)
        self.assertNotIn("5200", json.dumps(exported))
        self.assertEqual([row.get("emptyNameInHex") for row in exported[:7]],
                         [None, None, None, None, "00", "010000", None])
        self.assertEqual([row.get("omittedPayloads") for row in exported[:7]],
                         [["data_in"], ["data_in"], ["data_in"], ["data_in"], None, None, ["data_in"]])
        self.assertEqual([row.get("emptyNameOutHex") for row in exported[7:]], ["00", "010000"])
        self.assertTrue(all("dataInLE" not in row and "dataOutLE" not in row for row in exported))

    def test_empty_name_run_keeps_the_write_and_both_readbacks(self):
        ledger = rows("20261019-102738")
        self.assertEqual(ledger[5]["parameters"], [0xD18D])
        self.assertEqual(ledger[5]["omittedPayloads"], ["data_in"], "the bank's real name is never copied")
        self.assertNotIn("emptyNameInHex", ledger[5])
        self.assertEqual((ledger[32]["opcode"], ledger[32]["emptyNameOutHex"], ledger[32]["response"]),
                         ("0x1016", "00", "0x2001"))
        for index in (33, 34):
            self.assertEqual((ledger[index]["opcode"], ledger[index]["emptyNameInHex"], ledger[index]["response"]),
                             ("0x1015", "010000", "0x2001"))
        self.assertEqual((ledger[37]["kind"], ledger[37]["event"], ledger[37]["restoredSelector"]),
                         ("event", "selector_restored", 1))
        self.assertNotIn("recordedLocalTime", ledger[37])
        self.assertEqual((ledger[38]["opcode"], ledger[38]["outcome"]), ("0x1003", "recorded_ok"))
        self.assertFalse(any(row["opcode"] == "0x1016" and row["parameters"][0] in HELPER.BANK_CODES
                             for row in ledger if row["kind"] == "transaction" and row["parameters"]),
                         "no bank setting was written")
        manifest = json.loads((package("20261019-102738") / "manifest.json").read_text())
        self.assertEqual(manifest["coverage"]["emptyNamePayloadsRetained"], 3)
        self.assertEqual(manifest["coverage"]["payloadFieldsOmitted"], 2, "the name read and DeviceInfo")
        self.assertEqual(manifest["source"]["archivePath"],
                         "hardware-runs/bankprobe-x-t50-2026-10-19/logs/bankprobe-20261019-102738.json")

    def test_setting_writes_leave_both_empty_forms_in_place(self):
        ledger = rows("20261019-133848")
        for write, form in ((59, "00"), (73, "010000")):
            self.assertEqual((ledger[write]["opcode"], ledger[write]["emptyNameOutHex"], ledger[write]["response"]),
                             ("0x1016", form, "0x2001"))
            for read in (write + 1, write + 5, write + 9):
                self.assertEqual((ledger[read]["parameters"], ledger[read]["emptyNameInHex"]), ([0xD18D], "010000"))
            self.assertEqual((ledger[write + 3]["parameters"], ledger[write + 3]["dataOutLE"]), ([0xD192], "0200"))
            self.assertEqual((ledger[write + 7]["parameters"], ledger[write + 7]["dataOutLE"]), ([0xD192], "0b00"))
            self.assertEqual(ledger[write + 11]["omittedPayloads"], ["data_out"], "the original name is never copied")
        self.assertEqual(ledger[2], {"sourceIndex": 2, "kind": "event", "event": "experiment_context",
                                     "bank": 7, "autoUpdateReported": "unknown"})
        self.assertEqual((ledger[140]["event"], ledger[140]["exact"], ledger[140]["cleanupWrites"]),
                         ("bank_restore_verification", True, 0))
        self.assertEqual(set(ledger[140]["checkStatuses"].values()), {"exact"})
        self.assertEqual(len(ledger[140]["checkStatuses"]), 24)
        findings = json.loads((package("20261019-133848") / "findings.json").read_text())["findings"]
        self.assertEqual([trial["payloadHex"] for trial in findings["trials"]], ["00", "010000"])
        for trial in findings["trials"]:
            self.assertEqual([read["payloadHex"] for read in trial["readbacks"]], ["010000"] * 3)
        self.assertEqual(findings["persistenceAcrossPowerCycle"], "not_tested")

    def test_event_projections_keep_no_free_text_or_values(self):
        source = [{"event": "experiment context", "test": "PRIVATE_TEST", "auto_update": "off",
                   "auto_update_reported": "PRIVATE_ANSWER", "camera_state_reported": "PRIVATE_STATE", "bank": 7,
                   "model": "X-T50", "firmware": "1.32", "evidence": "PRIVATE_NOTE"},
                  {"event": "bank restore verification", "bank": 7, "exact": False, "persistence": "not tested",
                   "checks": [{"code": 0xD18D, "original": "PRIVATE_NAME", "read": "PRIVATE_OTHER", "status": "mismatched"}],
                   "writes": [{"code": 0xD18D, "rc": 0x2001}]}]
        exported = HELPER.ledger_rows(source)
        self.assertNotIn("PRIVATE_", json.dumps(exported))
        self.assertEqual(exported[0], {"sourceIndex": 0, "kind": "event", "event": "experiment_context",
                                       "bank": 7, "autoUpdateReported": "off"})
        self.assertEqual((exported[1]["exact"], exported[1]["checkStatuses"], exported[1]["cleanupWrites"]),
                         (False, {"0xD18D": "mismatched"}, 1))
        for bad in ({**source[0], "auto_update": "PRIVATE_ANSWER"},
                    {**source[1], "exact": "PRIVATE"},
                    {**source[1], "checks": [{"code": 0xD18D, "status": "PRIVATE_STATUS"}]}):
            with self.subTest(event=bad["event"]), self.assertRaises(ValueError):
                HELPER.ledger_rows([bad])

    def test_identity_payloads_excluded_even_if_short(self):
        source = [{"op": "0x1015", "params": [prop], "tid": i, "data_in": "0100",
                   "usb_error": "PRIVATE_ERROR", "name": "PRIVATE_NAME", "serial": "PRIVATE_SERIAL"}
                  for i, prop in enumerate(("0xD18D", "0xD186", "0xD187"))]
        source.append({"op": "0x1001", "params": [], "tid": 0, "response": "0x2001", "data_in": "PRIVATE_DEVICEINFO"})
        output = HELPER.ledger_rows(source)
        self.assertNotIn("PRIVATE_", json.dumps(output))
        self.assertTrue(all("dataInLE" not in row for row in output))
        self.assertEqual(output[0]["outcome"], "outcome_unknown")
        self.assertIsNone(output[0]["response"])
        for bad in ("", "0001020304", "PRIVATE_TEXT"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                HELPER.ledger_rows([{"op": "0x1015", "params": ["0xD190"], "tid": 1, "data_in": bad}])

    def test_wrong_hash_prevents_finding_projection(self):
        def should_not_run(_):
            self.fail("finding projection ran before source verification")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            HELPER.build_package(b"{}", {"evidenceId": "xt50-20261015-232441", "sourceSha256": "0" * 64}, should_not_run, __file__)

    def test_original_inside_checkout_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            HELPER.package_main({}, lambda _: None, __file__, [__file__, "--check"])
        self.assertIn("keep the original outside the repository", error.getvalue())

    def test_partial_teleconverter_comparison_preserves_refusal_and_noop(self):
        ledger = rows("20261015-232441")
        for index in (1555, 1564):
            self.assertEqual(ledger[index]["outcome"], "outcome_unknown")
            self.assertIsNone(ledger[index]["response"])
        for index, response in ((1562, "0x201C"), (1571, "0x2001")):
            self.assertEqual(ledger[index]["parameters"], [0xD18E])
            self.assertEqual(ledger[index]["dataOutLE"], "0700")
            self.assertEqual(ledger[index]["response"], response)
            self.assertEqual(ledger[index + 1]["dataInLE"], "0700")

    def test_oct15_final_snapshot_is_not_an_exact_restore(self):
        snapshots = json.loads((package("20261015-232441") / "snapshots.json").read_text())
        differences = {}
        for before, after in zip(snapshots["before"], snapshots["after"]):
            self.assertEqual(len(before["bankSettingsUnsigned"]), 23)
            self.assertNotIn("0xD1A5", before["bankSettingsUnsigned"])
            changed = {key: (value, after["bankSettingsUnsigned"][key])
                       for key, value in before["bankSettingsUnsigned"].items()
                       if value != after["bankSettingsUnsigned"][key]}
            if changed:
                differences[before["selectedBank"]] = changed
        self.assertEqual(differences, {7: {"0xD199": (4, 32776), "0xD19A": (9, 0),
                                           "0xD19B": (65527, 0), "0xD1A3": (1, 2)}})

    def test_oct16_control_readbacks_and_unknown_final_close(self):
        controls = {"20261016-094028": {36: "0200", 46: "0c00"},
                    "20261016-095611": {78: "0200", 115: "0c00", 151: "0200"},
                    "20261016-100752": {48: "0200"}}
        for run, expected in controls.items():
            with self.subTest(run=run):
                ledger = rows(run)
                for index, value in expected.items():
                    self.assertEqual(ledger[index]["parameters"], [0xD192])
                    self.assertEqual(ledger[index]["dataInLE"], value)
                self.assertEqual(ledger[-1]["opcode"], "0x1003")
                self.assertEqual(ledger[-1]["outcome"], "outcome_unknown")
                self.assertFalse((package(run) / "snapshots.json").exists())
                manifest = json.loads((package(run) / "manifest.json").read_text())
                self.assertEqual(manifest["coverage"]["topLevelSnapshotPair"], "not_recorded")


PILOT = Path(__file__).resolve().parents[1] / "evidence/xt50-20261015-224819"
PILOT_SPEC = importlib.util.spec_from_file_location("pilot_export", PILOT / "export.py")
PILOT_EXPORT = importlib.util.module_from_spec(PILOT_SPEC)
PILOT_SPEC.loader.exec_module(PILOT_EXPORT)


class PilotEvidencePackageTests(unittest.TestCase):
    def test_private_payloads_and_error_text_are_never_copied(self):
        source = []
        for index, prop in enumerate(("0xD18D", "0xD186", "0xD187")):
            source.append({"op": "0x1015", "params": [prop], "tid": index,
                           "data_in": "0100", "usb_error": "PRIVATE_ERROR_SENTINEL",
                           "name": "PRIVATE_BANK_SENTINEL", "serial": "PRIVATE_SERIAL_SENTINEL"})
        source.append({"op": "0x1001", "params": [], "tid": 4,
                       "response": "0x2001", "data_in": "PRIVATE_DEVICEINFO_SENTINEL"})
        exported = PILOT_EXPORT.ledger_rows(source)
        output = json.dumps(exported)
        self.assertNotIn("PRIVATE_", output)
        for row in exported:
            self.assertNotIn("dataInLE", row)
            self.assertEqual(row["omittedPayloads"], ["data_in"])
        self.assertEqual(exported[0]["outcome"], "outcome_unknown")
        self.assertIsNone(exported[0]["response"])

    def test_scalar_payload_limits_and_unknown_outcomes(self):
        row = {"op": "0x1016", "params": ["0xD190"], "tid": 1,
               "data_out": "6400", "usb_error": "PRIVATE_ERROR"}
        exported = PILOT_EXPORT.ledger_rows([row])[0]
        self.assertEqual(exported["dataOutLE"], "6400")
        self.assertEqual(exported["outcome"], "outcome_unknown")
        for bad in ("0001020304", "PRIVATE", "", "0x01"):
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                PILOT_EXPORT.ledger_rows([{**row, "data_out": bad}])

    def test_live_snapshot_is_separate_and_names_are_omitted(self):
        source = {"bank": 1, "taken": "2026-10-15T22:48:19", "name": "PRIVATE_NAME",
                  "props": {"0xD18E": "0x0007", "0xD1A5": "0x0009"}, "refused": {}}
        exported = PILOT_EXPORT.snapshot_rows([source])[0]
        self.assertEqual(exported["bankSettingsUnsigned"], {"0xD18E": 7})
        self.assertEqual(exported["liveSettingsUnsigned"], {"0xD1A5": 9})
        self.assertNotIn("PRIVATE_NAME", json.dumps(exported))

    def test_wrong_original_hash_is_rejected_before_export(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            PILOT_EXPORT.export_bundle(b'{"name":"PRIVATE_NAME"}')

    def test_reviewed_artifact_hashes_and_complete_order(self):
        manifest = json.loads((PILOT / "manifest.json").read_text())
        for name, metadata in manifest["artifacts"].items():
            content = (PILOT / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), metadata["sha256"])
            self.assertEqual(len(content), metadata["bytes"])
        self.assertEqual(hashlib.sha256((PILOT / "export.py").read_bytes()).hexdigest(),
                         manifest["transform"]["generatorSha256"])
        rows = [json.loads(line) for line in (PILOT / "transactions.jsonl").read_text().splitlines()]
        self.assertEqual([row["sourceIndex"] for row in rows], list(range(1692)))
        self.assertEqual(sum(row.get("outcome") == "outcome_unknown" for row in rows), 38)
        for row in rows:
            for key in ("dataInLE", "dataOutLE"):
                if key in row:
                    self.assertIn(row["parameters"][0], PILOT_EXPORT.SCALAR_CODES)
                    self.assertLessEqual(len(bytes.fromhex(row[key])), 4)

    def test_snapshot_comparison_does_not_claim_complete_restoration(self):
        snapshots = json.loads((PILOT / "snapshots.json").read_text())
        differences = {}
        for before, after in zip(snapshots["before"], snapshots["after"]):
            self.assertEqual(len(before["bankSettingsUnsigned"]), 23)
            self.assertNotIn("0xD1A5", before["bankSettingsUnsigned"])
            changed = {prop: (value, after["bankSettingsUnsigned"][prop])
                       for prop, value in before["bankSettingsUnsigned"].items()
                       if value != after["bankSettingsUnsigned"][prop]}
            if changed:
                differences[before["selectedBank"]] = changed
        self.assertEqual(differences, {7: {"0xD190": (200, 100), "0xD192": (12, 15), "0xD1A3": (1, 2)}})



CLIENT_RUN = EVIDENCE / "xt50-20261019-125007"
CLIENT_SPEC = importlib.util.spec_from_file_location("client_report_package", EVIDENCE / "client_report_package.py")
CLIENT = importlib.util.module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(CLIENT)


def client_rows():
    return [json.loads(line) for line in (CLIENT_RUN / "transactions.jsonl").read_text().splitlines()]


CLIENT_RUNS = {
    "20261019-125007": ("xt50-20261019-client-sources.json", "fuji-cookbook-camera-report-X-T50-20261019-1250.json", 339),
    "20261019-140542": ("xt50-20261019-140542-sources.json", "fuji-cookbook-camera-report-X-T50-20261019-1405.json", 325),
}


class ClientReportPackageTests(unittest.TestCase):
    def test_source_and_generator_and_data_integrity(self):
        for run, (inventory_name, report, count) in CLIENT_RUNS.items():
            with self.subTest(run=run):
                path = package(run)
                inventory = json.loads((EVIDENCE / inventory_name).read_text())
                manifest = json.loads((path / "manifest.json").read_text())
                source = {item["path"]: item for item in inventory["artifacts"]}["camera-reports/" + report]
                self.assertEqual(manifest["source"]["sha256"], source["sha256"])
                self.assertEqual(manifest["source"]["bytes"], source["bytes"])
                self.assertEqual(manifest["source"]["archivePath"], inventory["directory"] + "/" + source["path"])
                self.assertEqual(manifest["source"]["revision"], inventory["revision"])
                self.assertEqual(manifest["coverage"]["sourceEntries"], count)
                for name, metadata in manifest["artifacts"].items():
                    content = (path / name).read_bytes()
                    self.assertEqual(len(content), metadata["bytes"])
                    self.assertEqual(hashlib.sha256(content).hexdigest(), metadata["sha256"])
                for file_key, hash_key in (("generator", "generatorSha256"), ("sharedGenerator", "sharedGeneratorSha256"),
                                           ("helperModule", "helperModuleSha256")):
                    self.assertEqual(hashlib.sha256((path / manifest["transform"][file_key]).read_bytes()).hexdigest(),
                                     manifest["transform"][hash_key])

    def test_full_order_and_unknown_conditions_preserved(self):
        manifest = json.loads((CLIENT_RUN / "manifest.json").read_text())
        ledger = client_rows()
        self.assertEqual([row["sourceIndex"] for row in ledger], list(range(339)))
        self.assertEqual([row["sequence"] for row in ledger], list(range(1, 340)))
        self.assertEqual(manifest["coverage"]["outcomes"], {"recorded_ok": 339})
        self.assertEqual(manifest["coverage"]["emptyNamePayloadsRetained"], 1)
        self.assertIsNone(manifest["camera"]["usbMode"])
        self.assertEqual(manifest["conditions"]["autoUpdateCustomSetting"], "unknown")
        self.assertEqual(manifest["time"]["perTransactionTimestamps"], "absent")
        self.assertEqual(manifest["time"]["connectionIds"], "omitted")
        for row in ledger:
            self.assertNotIn("transactionId", row, "ImageCaptureCore numbers the wire transactions itself")
            for key in ("dataInLE", "dataOutLE"):
                if key in row:
                    self.assertIn(row["parameters"][0], HELPER.SCALAR_CODES)
                    self.assertLessEqual(len(bytes.fromhex(row[key])), 4)
            for key in ("emptyNameInHex", "emptyNameOutHex"):
                if key in row:
                    self.assertEqual(row["parameters"], [0xD18D])
                    self.assertIn(row[key], HELPER.EMPTY_NAME_PAYLOADS)
            if row["opcode"] not in ("0x1014", "0x1015", "0x1016"):
                self.assertNotIn("parameters", row)

    def test_restore_keeps_the_empty_name_write_the_setting_writes_and_both_name_reads(self):
        ledger = client_rows()
        by_sequence = {row["sequence"]: row for row in ledger}
        self.assertEqual((by_sequence[269]["parameters"], by_sequence[269]["dataOutLE"]), ([0xD18C], "0700"))
        for sequence in (294, 339):
            self.assertEqual(by_sequence[sequence]["parameters"], [0xD18D])
            self.assertEqual(by_sequence[sequence]["omittedPayloads"], ["data_in"], "the bank's name is never copied")
        write = by_sequence[295]
        self.assertEqual((write["opcode"], write["parameters"], write["emptyNameOutHex"], write["response"]),
                         ("0x1016", [0xD18D], "00", "0x2001"))
        writes = [by_sequence[sequence] for sequence in range(296, 316)]
        self.assertTrue(all(row["opcode"] == "0x1016" and row["parameters"][0] in HELPER.BANK_CODES
                            and row["response"] == "0x2001" for row in writes))
        self.assertFalse(any(by_sequence[sequence]["parameters"] in ([0xD18C], [0xD18D])
                             for sequence in range(296, 339)), "no selector change or name read in between")
        findings = json.loads((CLIENT_RUN / "findings.json").read_text())["findings"]
        self.assertEqual(findings["nameWrite"]["payloadHex"], "00")
        self.assertEqual(findings["settingWritesAfterName"]["count"], 20)
        self.assertEqual(findings["nameReadsBetweenWriteAndFinalRead"], 0)
        self.assertEqual((findings["nameAfterWrites"]["isEmptyForm"],
                          findings["nameAfterWrites"]["equalsNameBeforeWriteBytes"]), (False, True))

    def test_undo_writes_the_three_byte_form_and_the_bank_reads_unnamed(self):
        ledger = [json.loads(line) for line in (package("20261019-140542") / "transactions.jsonl").read_text().splitlines()]
        by_sequence = {row["sequence"]: row for row in ledger}
        self.assertEqual([row["sequence"] for row in ledger], list(range(1, 326)))
        for sequence in (161, 211, 325):
            self.assertEqual((by_sequence[sequence]["parameters"], by_sequence[sequence]["emptyNameInHex"]),
                             ([0xD18D], "010000"))
        for sequence in (212, 255, 281):
            self.assertIn(by_sequence[sequence]["omittedPayloads"], (["data_in"], ["data_out"]),
                          "the pushed name is never copied")
        write = by_sequence[282]
        self.assertEqual((write["opcode"], write["parameters"], write["emptyNameOutHex"], write["response"]),
                         ("0x1016", [0xD18D], "010000", "0x2001"))
        self.assertTrue(all(by_sequence[s]["opcode"] == "0x1016" and by_sequence[s]["parameters"][0] in HELPER.BANK_CODES
                            for s in range(283, 302)))
        self.assertFalse(any(by_sequence[s]["parameters"] in ([0xD18C], [0xD18D]) for s in range(283, 325)))
        findings = json.loads((package("20261019-140542") / "findings.json").read_text())["findings"]
        self.assertEqual(findings["undo"]["nameWrite"]["dataPhaseBytesHandedToTransport"], 3)
        self.assertEqual(findings["undo"]["settingWritesAfterName"]["count"], 19)
        self.assertEqual((findings["undo"]["nameAfterWrites"]["payloadHex"],
                          findings["undo"]["nameAfterWrites"]["isEmptyForm"]), ("010000", True))
        self.assertEqual(findings["clientRecords"]["undoOfC7"]["nameOutcome"], "written")

    def test_names_identity_and_omitted_lengths_are_never_copied(self):
        source = [
            {"sequence": 1, "operation": "0x1001", "parameters": [], "inData": "AB" * 64 + "…(+303 bytes)",
             "inDataLength": 367, "response": "0x2001", "durationMs": 13},
            {"sequence": 2, "operation": "0x1015", "parameters": ["0xD18D"], "inData": "0C430054002000500072000000",
             "inDataLength": 13, "response": "0x2001", "durationMs": 4},
            {"sequence": 3, "operation": "0x1016", "parameters": ["0xD18D"], "outDataLength": 23,
             "response": "0x2001", "durationMs": 79},
            {"sequence": 4, "operation": "0x1016", "parameters": ["0xD18D"], "outData": "00", "outDataLength": 1,
             "response": "0x2001", "durationMs": 76},
            {"sequence": 5, "operation": "0x1015", "parameters": ["0xD18D"], "inData": "010000", "inDataLength": 3,
             "response": "0x2001", "durationMs": 4},
            {"sequence": 6, "operation": "0x1015", "parameters": ["0xD186"], "inData": "0100", "inDataLength": 2,
             "response": "0x2001", "durationMs": 4},
            {"sequence": 7, "operation": "0x1008", "parameters": ["0x0002"], "inDataLength": 114,
             "response": None, "error": "PRIVATE_ERROR", "durationMs": 31},
            {"sequence": 8, "operation": "0x1016", "parameters": ["0xD192"], "outData": "0B00", "outDataLength": 2,
             "response": "0x201C", "durationMs": 9},
        ]
        exported = CLIENT.ledger_rows(source)
        text = json.dumps(exported)
        for private in ("PRIVATE_", "4300540020", "ABAB", "367", "114", "Length"):
            self.assertNotIn(private, text)
        self.assertEqual([row.get("omittedPayloads") for row in exported],
                         [["data_in"], ["data_in"], ["data_out"], None, None, ["data_in"], ["data_in"], None])
        self.assertEqual((exported[3]["emptyNameOutHex"], exported[4]["emptyNameInHex"]), ("00", "010000"))
        self.assertEqual((exported[6]["parameterCount"], exported[6]["outcome"], exported[6]["transportErrorRecorded"]),
                         (1, "outcome_unknown", True))
        self.assertNotIn("parameters", exported[6])
        self.assertEqual((exported[7]["dataOutLE"], exported[7]["outcome"]), ("0b00", "recorded_refusal"))
        for bad in ({"outData": "0B00", "outDataLength": 3}, {"outData": "0B0", "outDataLength": 2},
                    {"outData": "000102030405", "outDataLength": 6}):
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                CLIENT.ledger_rows([{"sequence": 1, "operation": "0x1016", "parameters": ["0xD192"],
                                     "response": "0x2001", "durationMs": 1, **bad}])

    def test_wrong_hash_prevents_finding_projection(self):
        def should_not_run(_):
            self.fail("finding projection ran before source verification")
        spec = {"evidenceId": "xt50-20261019-125007", "sourceSha256": "0" * 64,
                "sourceRevision": "0" * 40,
                "sourcePath": "hardware-runs/app-reports-x-t50/camera-reports/report.json"}
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            CLIENT.build_package(b"{}", spec, should_not_run, __file__)

    def test_original_inside_checkout_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            CLIENT.package_main({}, lambda _: None, __file__, [__file__, "--check"])
        self.assertIn("keep the original outside the repository", error.getvalue())

if __name__ == "__main__":
    unittest.main()
