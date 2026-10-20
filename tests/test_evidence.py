# SPDX-License-Identifier: MIT
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import validate_evidence as v


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads((ROOT/'evidence/example.synthetic.json').read_text())

    def test_example(self): self.assertEqual(v.validate_document(self.report),[])

    def test_missing_readback_cannot_be_verified(self):
        self.report['observations'][1]['verification']='matched'
        self.assertTrue(any('matched requires' in s for s in v.validate_document(self.report)))

    def test_empty_expected_not_a_pass(self):
        self.report['observations'][0]['expected']={}
        self.assertTrue(v.validate_document(self.report))

    def test_serial_fields_rejected(self):
        self.report['camera']['serial']='not-real'
        self.assertTrue(v.validate_document(self.report))

    def test_live_field_cannot_be_mislabeled_bank(self):
        self.report['observations'][0]['before']['bank:0xD1A5']='0700'
        self.assertTrue(v.validate_document(self.report))

    def test_bounded_trace_and_connection_provenance(self):
        self.report['trace']['droppedCount']=1
        self.report['observations'][0]['connectionId']='other'
        errors=v.validate_document(self.report)
        self.assertTrue(any('connection' in e for e in errors));self.assertTrue(any('truncated' in e for e in errors))

    def test_duplicate_keys_not_silently_overwritten(self):
        with self.assertRaises(ValueError): json.loads('{"x":1,"x":2}',object_pairs_hook=v.unique_object)

    def test_bad_date_and_response_rejected(self):
        self.report['connections'][0]['startedAt']='tomorrow'
        self.assertTrue(v.validate_document(self.report))
        self.report['connections'][0]['startedAt']='2026-10-17T12:00:00Z'
        self.report['observations'][0]['responseCode']=0x201c
        self.assertTrue(v.validate_document(self.report))


if __name__=='__main__': unittest.main()
