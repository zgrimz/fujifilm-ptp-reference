#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import package_main, scalar, transaction  # noqa: E402

SPEC = {"evidenceId": "gfx100s-20260915-181130",
        "sourceSha256": "87f8055ed3a98368bec8fdb43e258a44fc6f6afb80addf63cf31c979d9cd508e",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-15/fuji-cookbook-camera-report-GFX100S-20260915-1810.json",
        "transactionCount": 114}

BLOCK = ["0x%04X" % value for value in range(0xD18C, 0xD1A6)]
D183_DESCRIPTOR = {"dataType": "UINT16", "form": "enumeration", "enumeration": [0, 1], "factoryDefault": 65535,
                   "current": 65535, "writable": True}


def review(original, rows, records, observed):
    if (original["camera"]["firmwareVersion"], original["camera"]["identification"]) != ("1.32", "unknown") or \
            records["deviceInfo"]["deviceVersion"] != "1.32":
        raise ValueError("expected the fw 1.32 report from before the update")
    if any(entry["operation"] == "0x1016" for entry in original["transactions"]):
        raise ValueError("the reviewed trace writes nothing")
    parked = scalar(transaction(rows, 2, "0x1015", "0xD18C"), "in")
    image_size = scalar(transaction(rows, 10, "0x1015", "0xD18E"), "in")
    if (parked, image_size) != (7, 16):
        raise ValueError("expected the selector at 7 and Image Size 16")
    block_reads = [entry for entry in original["transactions"]
                   if entry["operation"] == "0x1015" and entry["parameters"][0] in BLOCK]
    if len(block_reads) != 53 or any(entry["response"] != "0x2001" for entry in block_reads):
        raise ValueError("expected every bank-block read answered")
    descriptors = observed["descriptorResponses"]
    if any(descriptors[prop] != {"0x200A": 2} for prop in BLOCK) or descriptors["0xD185"] != {"0x200A": 2} or \
            descriptors["0xD183"] != {"0x2001": 2}:
        raise ValueError("expected every bank-block descriptor refused and the D183 descriptor answered")
    for sequence in (6, 113):
        transaction(rows, sequence, "0x1015", "0xD183", "0x200A")
    for sequence in (8, 111):
        transaction(rows, sequence, "0x1015", "0xD185", "0x2002")
    sweep = {entry["property"]: entry for entry in records["propertySweep"]["entries"]}
    if sweep["0xD183"].get("descriptor") != D183_DESCRIPTOR:
        raise ValueError("expected the client's D183 descriptor")
    return {"firmwareReported": "1.32", "clientIdentification": "unknown",
            "getDeviceInfo": {"sequence": 1, "response": "0x2001", "durationMs": rows[1]["durationMs"],
                              "datasetBytes": records["deviceInfo"]["datasetBytes"]},
            "selectorWithoutAnyWrite": {"readSequence": 2, "valueUnsigned": parked, "selectorWritesInTrace": 0},
            "imageSizeAtThatSelector": {"readSequence": 10, "valueUnsigned": image_size},
            "bankBlockReads": {"count": len(block_reads), "allResponses": "0x2001"},
            "bankBlockDescriptors": {"properties": len(BLOCK), "requestsPerProperty": 2, "allResponses": "0x200A"},
            "d183": {"valueReadSequences": [6, 113], "valueResponse": "0x200A", "descriptorResponse": "0x2001",
                     "descriptor": D183_DESCRIPTOR,
                     "descriptorSource": "the client's property sweep; the ledger omits descriptor payloads"},
            "d185": {"valueReadSequences": [8, 111], "valueResponse": "0x2002", "descriptorResponse": "0x200A"},
            "notEstablished": ["USB mode", "why the selector read 7, a bank the fw 2.13 traces refuse to select",
                               "whether the block addressed a bank the camera shoots with",
                               "AUTO UPDATE CUSTOM SETTING, ISO, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
