# SPDX-License-Identifier: MIT
"""Fixture integrity for the synthetic tool test vectors; not hardware tests."""
import json
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/conformance"
REFERENCE_CHECKS = {
    "fixture_integrity", "jpeg_extractor", "extractor_json_round_trip",
    "bankprobe_transaction", "bankprobe_stream", "ptp_string", "bankprobe_write_policy",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate fixture JSON key: " + key)
        result[key] = value
    return result


def load(name):
    return json.loads((FIXTURES / name).read_text(), object_pairs_hook=unique_object)


class ConformanceFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {name: load(name) for name in
                         ("workflows.json", "jpeg-extractor.json", "binary.json")}

    def test_envelopes_ids_and_coverage_are_explicit(self):
        seen = set()
        kinds = {"workflows.json": {"workflow"}, "jpeg-extractor.json": {"jpeg-extractor"},
                 "binary.json": {"ptp-response", "ptp-usb-stream", "ptp-string"}}
        for name, doc in self.documents.items():
            self.assertEqual(doc["schema_version"], 1)
            self.assertEqual(doc["provenance"]["kind"], "synthetic")
            self.assertIs(doc["provenance"]["hardware_evidence"], False)
            self.assertTrue(doc["provenance"]["source"])
            self.assertTrue(doc["cases"])
            for case in doc["cases"]:
                with self.subTest(file=name, case=case["id"]):
                    self.assertRegex(case["id"], r"^[a-z][a-z0-9-]+$")
                    self.assertNotIn(case["id"], seen)
                    seen.add(case["id"])
                    self.assertIn(case["kind"], kinds[name])
                    self.assertIsInstance(case["input"], dict)
                    self.assertIsInstance(case["expected"], dict)
                    self.assertTrue(case["expected"])
                    coverage = case["coverage"]
                    self.assertEqual(set(coverage), {"reference"})
                    self.assertIsInstance(coverage["reference"], list)
                    self.assertEqual(len(coverage["reference"]), len(set(coverage["reference"])))
                    self.assertLessEqual(set(coverage["reference"]), REFERENCE_CHECKS)
                    self.assertIn("fixture_integrity", coverage["reference"])
                    # Every case is executed by a reference tool, not only checked for shape.
                    self.assertTrue(set(coverage["reference"]) - {"fixture_integrity"})

    def test_legacy_vectors_keep_their_existing_contract(self):
        doc = load("cases.json")
        self.assertEqual(set(doc), {"provenance", "write_results", "verification"})
        rows = doc["write_results"] + doc["verification"]
        self.assertEqual(len(rows), len({row["case"] for row in rows}))
        for row in doc["write_results"]:
            self.assertIn(row["expected"]["command"],
                          {"accepted", "refused", "outcome_unknown", "not_attempted"})
        for row in doc["verification"]:
            self.assertIn(row["state"], {"matched", "mismatched", "unavailable", "not_tested"})

    def test_workflow_events_and_control_assumptions(self):
        cases = {case["id"]: case for case in self.documents["workflows.json"]["cases"]}
        for case in cases.values():
            with self.subTest(case=case["id"]):
                self.assertIsInstance(case["policy"], str)
                self.assertTrue(case["input"]["initial"])
                events = set()
                for event in case["input"]["events"]:
                    self.assertNotIn(event["id"], events)
                    self.assertTrue(event["action"])
                    if "after" in event:
                        self.assertIn(event["after"], events)
                    if "outcome" in event:
                        self.assertIn(event["outcome"],
                                      {"accepted", "refused", "outcome_unknown", "succeeded", "failed"})
                    events.add(event["id"])
                self.assertTrue(events)
        for name in ("lost-bank-name-reply", "lost-bank-field-reply"):
            case = cases[name]
            self.assertIn(case["input"]["fault"]["property"],
                          {write["property"] for write in case["input"]["writes"]})
            self.assertEqual(case["input"]["fault"]["phase"], "after_delivery_before_reply")

    def test_jpeg_inputs_and_paths(self):
        scales = {"unknown", "direct", "times20", "heuristic"}
        for case in self.documents["jpeg-extractor.json"]["cases"]:
            with self.subTest(case=case["id"]):
                self.assertIn(case["input"]["extractor"]["wb_shift_scale"], scales)
                for tag in case["input"]["tags"]:
                    self.assertRegex(tag["tag"], r"^0x[0-9a-f]{4}$")
                    self.assertIn(tag["type"], {1, 2, 3, 4, 6, 7, 8, 9})
                    self.assertIn("value", tag)
                paths = []
                for assertion in case["expected"]["extractor"]:
                    self.assertTrue(assertion["path"])
                    self.assertIn("equals", assertion)
                    paths.append(tuple(assertion["path"]))
                self.assertEqual(len(paths), len(set(paths)))
                self.assertTrue(set(paths).isdisjoint(map(tuple, case["expected"].get("absent", []))))

    def test_binary_hex_and_mutations_match_the_named_controls(self):
        cases = {case["id"]: case for case in self.documents["binary.json"]["cases"]}
        for case in cases.values():
            with self.subTest(case=case["id"]):
                inputs = case["input"]
                encoded = inputs.get("chunks_hex", [inputs.get("hex")])
                for value in encoded:
                    if value is not None:
                        self.assertRegex(value, r"^(?:[0-9a-f]{2})*$")
                        bytes.fromhex(value)
                if "control" not in case:
                    continue
                control = cases[case["control"]]
                self.assertIs(control["expected"]["accepted"], True)
                original = bytes.fromhex(control["input"]["hex"])
                mutation = case["mutation"]
                if mutation["operation"] == "truncate":
                    self.assertGreaterEqual(mutation["length"], 0)
                    self.assertLess(mutation["length"], len(original))
                    changed = original[:mutation["length"]]
                elif mutation["operation"] == "replace":
                    replacement = bytes.fromhex(mutation["hex"])
                    offset = mutation["offset"]
                    self.assertGreaterEqual(offset, 0)
                    self.assertLessEqual(offset + len(replacement), len(original))
                    changed = original[:offset] + replacement + original[offset + len(replacement):]
                elif mutation["operation"] == "append":
                    changed = original + bytes.fromhex(mutation["hex"])
                else:
                    self.fail("unknown mutation: " + mutation["operation"])
                self.assertNotEqual(changed, original)
                self.assertEqual(changed, bytes.fromhex(inputs["hex"]))


if __name__ == "__main__":
    unittest.main()
