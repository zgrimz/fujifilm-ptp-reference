# SPDX-License-Identifier: MIT
"""Offline safety contracts; the synthetic camera is not hardware compatibility evidence."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("bankprobe", Path(__file__).resolve().parents[1] / "tools" / "bankprobe.py")
bp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bp)
CONFORMANCE = Path(__file__).resolve().parents[1] / "fixtures" / "conformance"


def conformance_cases(filename, coverage):
    document = json.loads((CONFORMANCE / filename).read_text())
    return [case for case in document["cases"] if coverage in case["coverage"]["reference"]]


class OfflineUSBError(Exception):
    """Finite synthetic input ended before the transaction could finish."""


class OfflineInputEndpoint:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def read(self, size, timeout):
        if not self.chunks:
            raise OfflineUSBError("synthetic input exhausted")
        return self.chunks.pop(0)


class OfflineOutputEndpoint:
    def __init__(self):
        self.writes = []

    def write(self, data, timeout):
        self.writes.append(bytes(data))


def endpoint_camera(chunks):
    """Use the actual stream reader and transaction parser; never discover USB."""
    cam = bp.Camera()
    cam._usb = SimpleNamespace(core=SimpleNamespace(USBError=OfflineUSBError))
    cam.ep_in = OfflineInputEndpoint(chunks)
    cam.ep_out = OfflineOutputEndpoint()
    return cam


class BinaryConformanceTests(unittest.TestCase):
    def test_response_and_stream_vectors_use_real_transaction_parser(self):
        for case in conformance_cases("binary.json", "bankprobe_transaction"):
            with self.subTest(case=case["id"]):
                incoming, expected = case["input"], case["expected"]
                if "chunks_hex" in incoming:
                    chunks = [bytes.fromhex(value) for value in incoming["chunks_hex"]]
                else:
                    chunks = [] if incoming["hex"] is None else [bytes.fromhex(incoming["hex"])]
                cam = endpoint_camera(chunks)
                request = incoming["request"]
                cam.tid = request["transaction_id"]
                if expected["accepted"]:
                    response, data, params = cam._transact_once(request["operation"])
                    self.assertEqual(response, expected["response_code"])
                    self.assertEqual(params, expected["parameters"])
                    self.assertEqual(data, None if expected.get("data_hex") is None
                                     else bytes.fromhex(expected["data_hex"]))
                    self.assertEqual(cam.pending, b"")
                else:
                    with self.assertRaisesRegex(bp.PTPError, expected["error_contains"]):
                        cam._transact_once(request["operation"])
                self.assertEqual(len(cam.ep_out.writes), 1)

    def test_coalesced_containers_are_retained_for_the_next_read(self):
        for case in conformance_cases("binary.json", "bankprobe_stream"):
            if "containers" not in case["expected"]:
                continue  # The transaction test above exercises these stream cases.
            with self.subTest(case=case["id"]):
                cam = endpoint_camera([bytes.fromhex(value) for value in case["input"]["chunks_hex"]])
                for expected in case["expected"]["containers"]:
                    self.assertEqual(cam._read_container(),
                                     (expected["type"], expected["code"], expected["transaction_id"],
                                      bytes.fromhex(expected["payload_hex"])))
                self.assertEqual(cam.pending, bytes.fromhex(case["expected"]["pending_hex"]))

    def test_string_vectors_use_real_ptp_string_decoder(self):
        for case in conformance_cases("binary.json", "ptp_string"):
            with self.subTest(case=case["id"]):
                raw, expected = bytes.fromhex(case["input"]["hex"]), case["expected"]
                if expected["accepted"]:
                    self.assertEqual(bp.parse_ptp_string(raw), (expected["text"], expected["consumed"]))
                else:
                    with self.assertRaisesRegex(ValueError, expected["error_contains"]):
                        bp.parse_ptp_string(raw)


def args(**overrides):
    values = dict(bank=1, other_bank=2, auto_update="off", camera_state="synthetic: C1, ISO500, JPEG",
                  no_restore=False, writes=["D192=2"])
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeCamera(bp.Camera):
    """Run the real reads, setters, preflight, restore and transaction policy without USB."""
    def __init__(self):
        super().__init__()
        self.info = {"model": "Synthetic", "device_version": "0"}
        props = {c: 0 for c in bp.BANK_PROPS}
        props.update({0xD18E: 7, 0xD18F: 2, 0xD190: 100, 0xD191: 0, 0xD192: 1,
                      0xD195: 1, 0xD199: 2, 0xD19C: 5300, 0xD1A3: 1, 0xD1A4: 1})
        self.banks = {k: {"name": bp.ptp_string("C%d original" % k), "props": dict(props)} for k in (1, 2, 3)}
        self.selector = 3
        self.live = 9
        self.writes = []
        self.missing = set()
        self.ignore = set()
        self.refuse = set()
        self.on_write = None
        self.on_read = None
        self.reconnect_hook = None
        self.recover_calls = 0

    def open(self):
        raise AssertionError("offline tests must never open USB")

    def start_session(self):
        pass

    def reconnect(self, *unused, **ignored):
        if self.reconnect_hook:
            self.reconnect_hook()

    def _recover(self):
        self.recover_calls += 1
        raise AssertionError("offline tests must not discover/recover USB")

    def _transact_once(self, operation, params=(), data=None):
        if operation in (bp.OP_OPEN_SESSION, bp.OP_CLOSE_SESSION):
            return 0x2001, None, []
        code = params[0]
        if operation == bp.OP_GET_PROP:
            if self.on_read:
                result = self.on_read(code)
                if result is not None:
                    return result
            if code in self.missing:
                return 0x200A, None, []
            if code == bp.BANK_SELECT:
                value = self.selector
            elif code == bp.BANK_NAME:
                return 0x2001, self.banks[self.selector]["name"], []
            elif code == bp.LIVE_IMAGE_SIZE:
                value = self.live
            else:
                value = self.banks[self.selector]["props"][code]
            return 0x2001, struct.pack("<H", value), []
        if operation != bp.OP_SET_PROP:
            raise AssertionError("unexpected operation")
        value = data if code == bp.BANK_NAME else struct.unpack("<H", data)[0]
        self.writes.append((self.selector, code, value))
        if code in self.refuse:
            return 0x201C, None, []
        if code not in self.ignore:
            if code == bp.BANK_SELECT:
                if value not in self.banks:
                    return 0x201C, None, []
                self.selector = value
            elif code == bp.BANK_NAME:
                self.banks[self.selector]["name"] = bytes(value)
            elif code == bp.LIVE_IMAGE_SIZE:
                self.live = value
            else:
                self.banks[self.selector]["props"][code] = value
        if self.on_write:
            self.on_write(code, value)
        return 0x2001, None, []

    @property
    def content_writes(self):
        return [row for row in self.writes if row[1] != bp.BANK_SELECT]


class BankprobeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = []

        def path(cam, bank):
            result = str(Path(self.temp.name) / ("bank-%d-%d.json" % (bank, len(self.paths))))
            self.paths.append(result)
            return result

        for name, replacement in (("backup_path", path), ("prompt", lambda text: None),
                                  ("menu_prompt", lambda text: None), ("ask", lambda text: "synthetic observation")):
            patcher = patch.object(bp, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        timer = patch.object(bp.time, "sleep", lambda seconds: None)
        timer.start()
        self.addCleanup(timer.stop)
        self.output = io.StringIO()
        quiet = contextlib.redirect_stdout(self.output)
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.cam = FakeCamera()

    def test_bank_snapshot_has_23_settings_and_no_live_value(self):
        snapshot = self.cam.read_bank(1)
        self.assertEqual(set(snapshot["props"]), set(range(0xD18E, 0xD1A5)))
        document = bp.bank_to_json(self.cam, snapshot)
        self.assertEqual(document["namespace"], "bank")
        self.assertNotIn("0xD1A5", document["props"])
        self.assertEqual(bp.json_to_bank(document)["props"], snapshot["props"])
        self.assertEqual(self.cam.read_live()["namespace"], "live")

    def test_generic_probe_restores_bank_and_selector_without_live_write(self):
        original = copy.deepcopy(self.cam.banks)
        rows = bp.cmd_probe(self.cam, args(writes=["D192=2", "D18D=temporary"]))
        self.assertTrue(all(row["ok"] for row in rows))
        self.assertEqual(self.cam.banks, original)
        self.assertEqual(self.cam.selector, 3)
        self.assertNotIn(bp.LIVE_IMAGE_SIZE, [c for _, c, _ in self.cam.writes])

    def test_entire_probe_list_is_validated_before_even_selector_write(self):
        for writes in (["D192=2", "D18C=2"], ["D192=2", "D1A5=7"], ["D192=2", "D017=1"],
                       ["D192=2", "bad"], ["D192=2", "D193=65536"], ["D18D=" + "x" * 255]):
            with self.subTest(writes=writes):
                cam = FakeCamera()
                with self.assertRaises(bp.PTPError):
                    bp.cmd_probe(cam, args(writes=writes))
                self.assertEqual(cam.writes, [])

    def test_missing_original_or_dependency_or_name_prevents_content_writes(self):
        for code in [bp.BANK_NAME] + bp.BANK_PROPS:
            with self.subTest(code=hex(code)):
                cam = FakeCamera()
                cam.missing.add(code)
                with self.assertRaises(bp.PTPError):
                    bp.cmd_probe(cam, args())
                self.assertEqual(cam.content_writes, [])
                self.assertEqual(cam.selector, 3)

    def test_every_registered_write_trial_uses_preflight(self):
        for name, (fn, kind, _) in bp.TESTS.items():
            if kind not in {"WRITE", "one write"}:
                continue
            with self.subTest(name=name):
                cam = FakeCamera()
                cam.missing.add(0xD192)
                with self.assertRaises(bp.PTPError):
                    fn(cam, args(), bp.Report())
                self.assertEqual(cam.content_writes, [])
                self.assertEqual(cam.selector, 3)

    def test_missing_selector_prevents_all_writes(self):
        self.cam.missing.add(bp.BANK_SELECT)
        with self.assertRaises(bp.PTPError):
            bp.cmd_probe(self.cam, args())
        self.assertEqual(self.cam.writes, [])

    def test_backup_disk_failure_prevents_content_writes(self):
        with patch.object(bp, "save_backup", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                bp.cmd_probe(self.cam, args())
        self.assertEqual(self.cam.content_writes, [])
        self.assertEqual(self.cam.selector, 3)

    def test_interruption_and_skip_run_cleanup_on_real_name_last_path(self):
        for failure in (bp.SkipTest(), KeyboardInterrupt(), bp.PTPError("controlled failure")):
            with self.subTest(failure=type(failure).__name__):
                cam = FakeCamera()
                original = copy.deepcopy(cam.banks)
                def stop():
                    raise failure
                cam.reconnect_hook = stop
                with self.assertRaises(type(failure)):
                    bp.test_name_last(cam, args(), bp.Report())
                self.assertEqual(cam.banks, original)
                self.assertEqual(cam.selector, 3)
                self.assertIsNone(cam.experiment)

    def test_selector_drift_stops_write_and_cleanup_reselects_target(self):
        original = copy.deepcopy(self.cam.banks)
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]):
                self.cam.selector = 2  # another actor moved the device selector
                with self.assertRaisesRegex(bp.PTPError, "selector changed"):
                    self.cam.write_verify(0xD192, 2)
        self.assertEqual(self.cam.banks, original)
        self.assertEqual(self.cam.content_writes, [])
        self.assertEqual(self.cam.selector, 3)

    def test_ignored_selector_ok_cannot_redirect_recipe_write(self):
        self.cam.ignore.add(bp.BANK_SELECT)
        with self.assertRaises(bp.PTPError):
            bp.cmd_probe(self.cam, args())
        self.assertEqual(self.cam.content_writes, [])

    def test_finally_restore_reselects_original_target_after_observing_other_bank(self):
        original = copy.deepcopy(self.cam.banks)
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]):
                self.cam.write_verify(0xD192, 2)
                self.cam.select_bank(2)
        self.assertEqual(self.cam.banks, original)
        self.assertFalse(any(bank == 2 and code != bp.BANK_SELECT for bank, code, _ in self.cam.writes))

    def test_explicit_live_trial_restores_separate_original(self):
        original = copy.deepcopy(self.cam.banks)
        bp.test_d1a5_live(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.live, 9)
        self.assertEqual(self.cam.banks, original)
        live_writes = [value for _, code, value in self.cam.writes if code == bp.LIVE_IMAGE_SIZE]
        self.assertEqual(live_writes, [7, 9])
        files = list(Path(self.temp.name).glob("*-live.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text())["namespace"], "live")

    def test_live_write_is_refused_without_explicit_snapshot(self):
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]):
                with self.assertRaisesRegex(bp.PTPError, "explicit live snapshot"):
                    self.cam.write_verify(bp.LIVE_IMAGE_SIZE, 7)
        self.assertNotIn(bp.LIVE_IMAGE_SIZE, [c for _, c, _ in self.cam.writes])

    def test_unreadable_live_original_blocks_live_trial_before_content(self):
        self.cam.missing.add(bp.LIVE_IMAGE_SIZE)
        with self.assertRaisesRegex(bp.PTPError, "live Image Size original"):
            bp.test_d1a5_live(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.content_writes, [])

    def test_two_bank_trial_preflights_and_cleans_both_banks(self):
        original = copy.deepcopy(self.cam.banks)
        bp.test_heif_scope(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.banks, original)
        self.assertEqual({bank for bank, code, _ in self.cam.content_writes}, {1, 2})
        self.assertEqual(self.cam.selector, 3)

    def test_second_bank_missing_original_blocks_all_content(self):
        def missing_second(code):
            if self.cam.selector == 2 and code == 0xD1A2:
                return 0x200A, None, []
        self.cam.on_read = missing_second
        with self.assertRaises(bp.PTPError):
            bp.test_heif_scope(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.content_writes, [])

    def test_restore_turns_current_priority_off_before_dr_then_restores_priority(self):
        self.cam.banks[1]["props"][0xD191] = 0x8000
        saved = self.cam.read_bank(1)
        self.cam.banks[1]["props"][0xD190] = 200
        result = bp.restore_bank(self.cam, saved)
        writes = [(code, value) for _, code, value in self.cam.content_writes if code != bp.BANK_NAME]
        self.assertEqual(writes, [(0xD191, 0), (0xD190, 100), (0xD191, 0x8000)])
        self.assertTrue(result["exact"])

    def test_restore_does_not_normalize_untouched_remembered_grain(self):
        self.cam.banks[1]["props"][0xD195] = 6
        original = copy.deepcopy(self.cam.banks)
        bp.cmd_probe(self.cam, args())
        self.assertEqual(self.cam.banks, original)
        self.assertNotIn(0xD195, [c for _, c, _ in self.cam.content_writes])

    def test_lossy_grain_restore_is_reported_not_promised_exact(self):
        self.cam.banks[1]["props"][0xD195] = 6
        saved = self.cam.read_bank(1)
        self.cam.banks[1]["props"][0xD195] = 2
        result = bp.restore_bank(self.cam, saved)
        grain = next(c for c in result["checks"] if c["code"] == 0xD195)
        self.assertEqual(grain["status"], "semantic-only")
        self.assertFalse(result["exact"])

    def test_known_lossy_grain_write_refuses_whole_generic_list(self):
        self.cam.banks[1]["props"][0xD195] = 6
        with self.assertRaisesRegex(bp.PTPError, "whole probe list is refused"):
            bp.cmd_probe(self.cam, args(writes=["D192=2", "D195=2"]))
        self.assertEqual(self.cam.content_writes, [])

    def test_restore_final_mismatch_and_unavailable_are_distinct(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable):
                cam = FakeCamera()
                saved = cam.read_bank(1)
                cam.banks[1]["props"][0xD192] = 2
                cam.ignore.add(0xD192)
                if unavailable:
                    cam.missing.add(0xD192)
                result = bp.restore_bank(cam, saved)
                check = next(c for c in result["checks"] if c["code"] == 0xD192)
                self.assertEqual(check["status"], "unavailable" if unavailable else "mismatched")
                self.assertFalse(result["exact"])

    def test_inactive_changed_field_is_included_in_final_verification(self):
        saved = self.cam.read_bank(1)
        self.cam.banks[1]["props"][0xD193] = 10
        result = bp.restore_bank(self.cam, saved)
        self.assertEqual(next(c for c in result["checks"] if c["code"] == 0xD193)["status"], "mismatched")
        self.assertFalse(result["exact"])

    def test_restore_name_preserves_original_wire_representation(self):
        self.cam.banks[1]["name"] = b"\x01\x00\x00"  # noncanonical, valid empty PTP string
        original = copy.deepcopy(self.cam.banks)
        bp.cmd_probe(self.cam, args(writes=["D18D=temporary"]))
        self.assertEqual(self.cam.banks, original)

    def test_malformed_strings_are_not_backup_originals(self):
        for raw in (b"", b"\x04A\x00", b"\x02A\x00B\x00", b"\x02\x00\xd8\x00\x00"):
            with self.subTest(raw=raw):
                cam = FakeCamera()
                cam.banks[1]["name"] = raw
                with self.assertRaises(bp.PTPError):
                    bp.cmd_probe(cam, args())
                self.assertEqual(cam.content_writes, [])

    def test_uncertain_write_is_never_replayed_or_classified_unattempted(self):
        def fault(code, value):
            if code == 0xD192:
                error = bp.PTPError("lost USB after delivery")
                error.usb = True
                raise error
        self.cam.on_write = fault
        with self.assertRaisesRegex(bp.PTPError, "possibly sent; outcome unknown"):
            bp.cmd_probe(self.cam, args())
        self.assertEqual(len([r for r in self.cam.content_writes if r[1] == 0xD192]), 1)
        self.assertEqual(self.cam.recover_calls, 0)
        self.assertTrue(self.cam.write_uncertain)
        self.assertTrue(any(r["event"] == "bank restore unavailable" for r in self.cam.log))

    def test_lost_bank_reply_workflows_stop_later_writes_cleanup_and_next_bank(self):
        for case in conformance_cases("workflows.json", "bankprobe_write_policy"):
            with self.subTest(case=case["id"]):
                incoming, expected = case["input"], case["expected"]
                self.assertEqual(incoming["fault"]["phase"], "after_delivery_before_reply")
                cam = FakeCamera()
                bank = incoming["initial"]["target_bank"]
                fault_property = int(incoming["fault"]["property"], 16)
                writes = ["%s=%s" % (write["property"], write["value"])
                          for write in incoming["writes"]]
                interrupted_experiments = []

                def lose_reply(code, value):
                    if code == fault_property:
                        interrupted_experiments.append(cam.experiment)
                        error = bp.PTPError("synthetic reply lost after delivery")
                        error.usb = True
                        raise error

                cam.on_write = lose_reply
                with self.assertRaisesRegex(bp.PTPError, "possibly sent; outcome unknown"):
                    bp.cmd_probe(cam, args(bank=bank, writes=writes))
                # The simulator applied the first write before losing its reply. The
                # production transaction policy must not infer successful verification.
                first = incoming["writes"][0]
                value = bp.ptp_string(first["value"]) if fault_property == bp.BANK_NAME else first["value"]
                self.assertEqual(cam.content_writes, [(bank, fault_property, value)])
                self.assertTrue(cam.write_uncertain)
                self.assertTrue(cam.cleanup_failed)
                self.assertEqual(cam.recover_calls, 0)
                self.assertTrue(any(row.get("event") == "write outcome unknown" for row in cam.log))
                self.assertTrue(any(row.get("event") == "bank restore unavailable" for row in cam.log))
                self.assertEqual(len(interrupted_experiments), 1)
                outcomes = interrupted_experiments[0].outcomes
                self.assertEqual(outcomes, [])  # No successful readback is reported.
                sent = list(cam.writes)
                with self.assertRaisesRegex(bp.PTPError, "previous cleanup/delivery"):
                    bp.cmd_probe(cam, args(bank=2, writes=["D192=2"]))
                self.assertEqual(cam.writes, sent)
                actual = {
                    "command": "outcome_unknown" if cam.write_uncertain else "known",
                    "verification": "unavailable" if not outcomes else outcomes[-1]["outcome"],
                    "later_writes": "not_attempted" if len(cam.content_writes) == 1 else "attempted",
                    "automatic_cleanup": "not_attempted" if len(cam.content_writes) == 1 else "attempted",
                    "next_bank": "not_attempted" if cam.writes == sent else "attempted",
                    "recovery": "unresolved" if cam.cleanup_failed else "resolved",
                }
                self.assertEqual(actual, expected)

    def test_keyboard_interrupt_during_sent_write_blocks_replay_and_cleanup(self):
        def interrupt(code, value):
            if code == 0xD192:
                raise KeyboardInterrupt()
        self.cam.on_write = interrupt
        with self.assertRaises(KeyboardInterrupt):
            bp.cmd_probe(self.cam, args())
        self.assertEqual(self.cam.banks[1]["props"][0xD192], 2)
        self.assertEqual(len(self.cam.content_writes), 1)
        self.assertTrue(self.cam.write_uncertain)
        self.assertTrue(self.cam.cleanup_failed)
        self.assertEqual(self.cam.recover_calls, 0)
        self.assertTrue(any(r["event"] == "write outcome unknown" and r.get("interrupted") for r in self.cam.log))

    def test_keyboard_interrupt_during_cleanup_is_preserved(self):
        def interrupt_restore(code, value):
            if code == 0xD192 and value == 1:
                raise KeyboardInterrupt()
        self.cam.on_write = interrupt_restore
        with self.assertRaises(KeyboardInterrupt):
            bp.cmd_probe(self.cam, args())
        self.assertTrue(self.cam.write_uncertain)
        self.assertTrue(self.cam.cleanup_failed)

    def test_nonexact_cleanup_stops_sequence_before_second_trial(self):
        def ignore_restore(code, value):
            if code == 0xD192 and value == 2:
                self.cam.ignore.add(0xD192)
        self.cam.on_write = ignore_restore
        with self.assertRaisesRegex(bp.PTPError, "cleanup not exact"):
            bp.run_tests(self.cam, args(), ["name-last", "dr-zero"])
        self.assertTrue(self.cam.cleanup_failed)
        self.assertNotIn(0xD190, [code for _, code, _ in self.cam.content_writes])
        self.assertEqual(self.cam.selector, 3)
        count = len(self.cam.content_writes)
        with self.assertRaisesRegex(bp.PTPError, "previous cleanup/delivery"):
            bp.cmd_probe(self.cam, args())
        self.assertEqual(len(self.cam.content_writes), count)

    def test_expected_refusal_with_exact_cleanup_may_continue_sequence(self):
        self.cam.refuse.add(0xD190)
        findings = bp.run_tests(self.cam, args(), ["dr-zero", "name-last"])
        self.assertFalse(self.cam.cleanup_failed)
        self.assertIn(0xD192, [code for _, code, _ in self.cam.content_writes])
        self.assertTrue(any(r["test"] == "name-last" for r in findings))

    def test_no_restore_requires_verified_success_and_rolls_back_on_error(self):
        bp.cmd_probe(self.cam, args(no_restore=True))
        self.assertEqual(self.cam.banks[1]["props"][0xD192], 2)
        self.assertEqual(self.cam.selector, 3)
        cam = FakeCamera()
        original = copy.deepcopy(cam.banks)
        cam.ignore.add(0xD192)
        with self.assertRaisesRegex(bp.PTPError, "rolling back"):
            bp.cmd_probe(cam, args(no_restore=True))
        self.assertEqual(cam.banks, original)

    def test_v2_validation_rejects_legacy_live_and_invalid_values_before_writes(self):
        snapshot = self.cam.read_bank(1)
        good = bp.bank_to_json(self.cam, snapshot)
        for mutate in (lambda d: d.pop("schema_version"), lambda d: d["props"].update({"0xD1A5": "0x0007"}),
                       lambda d: d["props"].update({"0xD192": "0x10000"}), lambda d: d.update(name=None)):
            document = copy.deepcopy(good)
            mutate(document)
            with self.assertRaises(bp.PTPError):
                bp.json_to_bank(document)

    def test_restore_file_validated_before_camera_mutation(self):
        path = Path(self.temp.name) / "invalid.json"
        path.write_text('{"schema_version": 1}')
        with self.assertRaises(bp.PTPError):
            bp.cmd_restore(self.cam, args(file=str(path)))
        self.assertEqual(self.cam.writes, [])

    def test_duplicate_json_keys_are_rejected_before_any_camera_write(self):
        document = bp.bank_to_json(self.cam, self.cam.read_bank(1))
        good = json.dumps(document)
        self.cam.writes.clear()
        variants = [good.replace('"0xD192": "0x0001"', '"0xD192": "0x0002", "0xD192": "0x0001"'),
                    good.replace('"bank": 1', '"bank": 2, "bank": 1')]
        path = Path(self.temp.name) / "duplicate.json"
        for source in variants:
            with self.subTest(source=source):
                path.write_text(source)
                with self.assertRaisesRegex(bp.PTPError, "duplicate JSON key"):
                    bp.cmd_restore(self.cam, args(file=str(path)))
                self.assertEqual(self.cam.writes, [])

    def test_restore_file_captures_current_original_and_checks_model(self):
        saved = self.cam.read_bank(1)
        saved["props"][0xD192] = 2
        path = Path(self.temp.name) / "valid.json"
        document = bp.bank_to_json(self.cam, saved)
        path.write_text(json.dumps(document))
        self.cam.selector = 3
        result = bp.cmd_restore(self.cam, args(file=str(path)))
        self.assertTrue(result["exact"])
        self.assertEqual(self.cam.banks[1]["props"][0xD192], 2)
        self.assertEqual(self.cam.selector, 3)
        document["model"] = "Different"
        path.write_text(json.dumps(document))
        self.cam.writes.clear()
        with self.assertRaises(bp.PTPError):
            bp.cmd_restore(self.cam, args(file=str(path)))
        self.assertEqual(self.cam.writes, [])

    def test_auto_update_state_is_recorded_and_unknown_limits_conclusion(self):
        rep = bp.Report()
        bp.test_no_name_control(self.cam, args(auto_update="unknown"), rep)
        self.assertEqual(rep.findings[0]["context"]["auto_update"], "unknown")
        self.assertIn("persistence interpretation limited", rep.findings[0]["verdict"])
        self.assertNotIn("is what commits", rep.findings[0]["verdict"])

    def test_live_unsaved_experiment_requires_confirmed_auto_update_off(self):
        for value in ("on", "unknown"):
            with self.assertRaisesRegex(bp.PTPError, "requires operator-confirmed"):
                bp.test_d1a5_live(self.cam, args(auto_update=value), bp.Report())
        self.assertEqual(self.cam.writes, [])

    def test_missing_observation_is_inconclusive_not_a_negative_hardware_fact(self):
        rep = bp.Report()
        rep.add("example", "value did not persist", {"after": None})
        self.assertTrue(rep.findings[0]["verdict"].startswith("inconclusive"))

    def test_dr_placeholder_requires_confirmed_priority_and_final_dr_readback(self):
        # These menu-driven snapshots test inference only, not camera behavior.
        cases = [
            ("priority never enabled", (0xFFFF, 0), (0xFFFF, 0), "inconclusive"),
            ("Auto may persist", (0xFFFF, 2), (0xFFFF, 0), "inconclusive"),
            ("priority never disabled", (0xFFFF, 2), (100, 2), "inconclusive"),
            ("profile code is not bank priority", (0xFFFF, 3), (100, 0), "inconclusive"),
            ("other final DR", (0xFFFF, 2), (200, 0), "inconclusive"),
            ("temporary sentinel", (0xFFFF, 2), (100, 0), "consistent with a temporary placeholder"),
            ("temporary sentinel with Auto", (0xFFFF, 0x8000), (100, 0), "consistent with a temporary placeholder"),
            ("DR unchanged", (100, 0x8000), (100, 0), "no 0xFFFF placeholder observed"),
        ]
        for label, on, off_again, expected in cases:
            with self.subTest(case=label):
                cam, rep = FakeCamera(), bp.Report()
                states = iter(((100, 0), on, off_again))

                def change_menu(unused):
                    dr, priority = next(states)
                    cam.banks[1]["props"].update({0xD190: dr, 0xD191: priority})

                with patch.object(bp, "menu_prompt", side_effect=change_menu) as menu:
                    bp.test_dr_placeholder(cam, args(), rep)
                finding = rep.findings[0]
                self.assertIn(expected, finding["verdict"])
                self.assertEqual(finding["detail"]["readbacks"], {
                    "off": {"0xD190": 100, "0xD191": 0},
                    "on": {"0xD190": on[0], "0xD191": on[1]},
                    "off_again": {"0xD190": off_again[0], "0xD191": off_again[1]},
                })
                self.assertEqual(menu.call_count, 3)
                self.assertEqual(cam.selector, 3)
                self.assertEqual(cam.content_writes, [])

    def test_dr_placeholder_missing_final_readback_stays_inconclusive(self):
        snapshots = [self.cam.read_bank(1) for _ in range(3)]
        snapshots[1]["props"].update({0xD190: 0xFFFF, 0xD191: 2})
        snapshots[2]["props"].update({0xD190: None, 0xD191: 0})
        rep = bp.Report()
        with patch.object(self.cam, "read_bank", side_effect=snapshots):
            bp.test_dr_placeholder(self.cam, args(), rep)
        self.assertTrue(rep.findings[0]["verdict"].startswith("inconclusive"))
        self.assertIsNone(rep.findings[0]["detail"]["readbacks"]["off_again"]["0xD190"])

    def test_live_observation_does_not_reverse_established_path_identity(self):
        rep = bp.Report()
        self.cam.live = 7
        bp.test_d1a5_live(self.cam, args(), rep)
        self.assertNotIn("NOT the live", self.output.getvalue())
        self.assertIn("agreement was not observed", rep.findings[0]["verdict"])

    def test_read_only_menu_sweep_restores_selector_after_skip(self):
        with patch.object(bp, "menu_prompt", side_effect=bp.SkipTest()):
            with self.assertRaises(bp.SkipTest):
                bp.test_filmsim(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.selector, 3)
        self.assertEqual(self.cam.content_writes, [])

    def test_all_named_trials_execute_offline_without_runtime_errors(self):
        # Menu observations are synthetic no-ops; some trials correctly report incomplete cleanup.
        for name, (fn, _, _) in bp.TESTS.items():
            with self.subTest(name=name):
                cam = FakeCamera()
                try:
                    fn(cam, args(), bp.Report())
                except bp.PTPError as error:
                    self.assertIn("cleanup not exact", str(error))
                self.assertIsNone(cam.experiment)
                self.assertEqual(cam.selector, 3)

    def test_malformed_snapshot_shapes_fail_before_camera_write(self):
        for value in (None, [], {"props": []}, {"schema_version": 2, "namespace": "bank", "props": {}}):
            with self.subTest(value=value):
                with self.assertRaises(bp.PTPError):
                    bp.json_to_bank(value)
        self.assertEqual(self.cam.writes, [])

    def test_name_write_acknowledged_but_ignored_is_not_verified(self):
        self.cam.ignore.add(bp.BANK_NAME)
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]) as exp:
                self.cam.set_str(bp.BANK_NAME, "ignored")
                self.assertEqual(exp.outcomes[-1]["outcome"], "mismatched")
                self.assertFalse(exp.outcomes[-1]["ok"])

    def test_reconnect_identity_mismatch_blocks_cleanup_writes(self):
        for method in (bp.Camera.reconnect, bp.Camera._recover):
            with self.subTest(method=method.__name__):
                cam = FakeCamera()
                def different_camera():
                    cam.info = {"model": "Different", "device_version": "1"}
                with patch.object(cam, "open", different_camera):
                    with self.assertRaisesRegex(bp.PTPError, "identity/firmware changed"):
                        if method is bp.Camera.reconnect:
                            method(cam, "reconnect")
                        else:
                            method(cam)
                self.assertTrue(cam.write_uncertain)
                with self.assertRaises(bp.PTPError):
                    cam.set_u16(bp.BANK_SELECT, 1)
                self.assertEqual(cam.writes, [])

    def test_selector_cleanup_failure_is_not_a_success(self):
        with self.assertRaisesRegex(bp.PTPError, "selector reads back"):
            with bp.preserve_selector(self.cam):
                self.cam.select_bank(1)
                self.cam.ignore.add(bp.BANK_SELECT)
        self.assertTrue(any(r["event"] == "selector restoration unavailable" for r in self.cam.log))

    def test_current_baseline_cannot_mutate_original_backup(self):
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]) as exp:
                baseline, _ = bp._backup_and_select(self.cam, 1)
                baseline["props"][0xD192] = 19
                self.assertEqual(exp.banks[1]["props"][0xD192], 1)
                document = json.loads(Path(self.paths[0]).read_text())
                self.assertEqual(document["props"]["0xD192"], "0x0001")

    @staticmethod
    def answer_names_like_an_x_t50(cam, setting_write_restores_name=False):
        """An emptied name reads back as 01 00 00 (bankprobe, X-T50 fw 1.32, 2026-10-19)."""
        named = {k: bank["name"] for k, bank in cam.banks.items()}

        def on_write(code, value):
            bank = cam.banks[cam.selector]
            if code == bp.BANK_NAME:
                if bytes(value) in bp.EMPTY_NAME_FORMS:
                    bank["name"] = b"\x01\x00\x00"
                else:
                    named[cam.selector] = bytes(value)
            elif setting_write_restores_name and code in bp.BANK_PROPS:
                bank["name"] = named[cam.selector]
        cam.on_write = on_write

    def test_empty_name_reads_each_form_after_a_setting_write_and_restores_the_bank(self):
        self.answer_names_like_an_x_t50(self.cam)
        original = copy.deepcopy(self.cam.banks)
        rep = bp.Report()
        bp.test_empty_name(self.cam, args(), rep)
        forms = rep.findings[-1]["detail"]["forms"]
        for key in ("00", "010000"):
            self.assertEqual((forms[key]["write_rc"], forms[key]["restore_rc"]), (0x2001, 0x2001))
            self.assertEqual([forms[key][step] for step in ("written", "after_setting", "after_setting_back", "name_restored")],
                             ["count and NUL", "count and NUL", "count and NUL", "original"])
        name_writes = [value for _, code, value in self.cam.content_writes if code == bp.BANK_NAME]
        original_name = original[1]["name"]
        self.assertEqual(name_writes, [b"\x00", original_name, b"\x01\x00\x00", original_name])
        self.assertEqual([value for _, code, value in self.cam.content_writes if code == 0xD192], [2, 1, 2, 1])
        self.assertEqual(self.cam.banks, original)
        self.assertEqual(self.cam.selector, 3)
        self.assertIsNone(self.cam.experiment)
        detail = json.dumps(rep.findings[-1]["detail"])
        self.assertNotIn("C1 original", detail)
        self.assertNotIn(original_name.hex(), detail)

    def test_empty_name_shows_a_setting_write_bringing_the_old_name_back(self):
        self.answer_names_like_an_x_t50(self.cam, setting_write_restores_name=True)
        rep = bp.Report()
        bp.test_empty_name(self.cam, args(), rep)
        for form in rep.findings[-1]["detail"]["forms"].values():
            self.assertEqual((form["written"], form["after_setting"]), ("count and NUL", "original"))

    def test_empty_name_needs_a_named_bank_before_any_content_write(self):
        self.cam.banks[1]["name"] = b"\x01\x00\x00"
        with self.assertRaisesRegex(bp.PTPError, "has no name"):
            bp.test_empty_name(self.cam, args(), bp.Report())
        self.assertEqual(self.cam.content_writes, [])
        self.assertEqual(self.cam.selector, 3)

    def test_empty_name_writes_only_empty_forms_or_the_original_bytes(self):
        with bp.preserve_selector(self.cam):
            with bp.BankExperiment(self.cam, [1]):
                with self.assertRaisesRegex(bp.PTPError, "only an empty encoding"):
                    bp._write_name_bytes(self.cam, bp.ptp_string("invented"), self.cam.banks[1]["name"])
        self.assertEqual(self.cam.content_writes, [])

    def test_selftest_runs_without_usb(self):
        with patch.object(bp.Camera, "open", side_effect=AssertionError("USB forbidden")):
            self.assertEqual(bp.main(["selftest"]), 0)


if __name__ == "__main__":
    unittest.main()
