#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import bank_pass, package_main, scalar, transaction  # noqa: E402

SPEC = {"evidenceId": "gfx100s-20260915-194552",
        "sourceSha256": "144c2951b93280c5c1c29761e7f51dac166da6b0cabaf6ba91418cd2a9ec9c94",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-15/fuji-cookbook-camera-report-GFX100S-20260915-1945.json",
        "transactionCount": 244}

# The grain probe as the trace records it: each write, its response, and the read that follows it.
PROBE = [(0, "0x201C", 3), (2, "0x2001", 2), (1, "0x2001", 6), (3, "0x2001", 3), (6, "0x201C", 3),
         (4, "0x2001", 4), (7, "0x201C", 4), (5, "0x2001", 5), (1, "0x2001", 7), (8, "0x201C", 7)]


def review(original, rows, records, observed):
    if original["camera"]["firmwareVersion"] != "2.13" or records["deviceInfo"]["deviceVersion"] != "2.13":
        raise ValueError("expected firmware 2.13")
    banks = bank_pass(rows, 2)
    if scalar(transaction(rows, 164, "0x1016", "0xD18C", "0x200A"), "out") != 7 or \
            scalar(transaction(rows, 165, "0x1016", "0xD18C"), "out") != 1:
        raise ValueError("expected bank 7 refused and bank 1 selected after it")
    if scalar(transaction(rows, 223, "0x1016", "0xD18C"), "out") != 1:
        raise ValueError("expected the grain probe on C1")
    before = scalar(transaction(rows, 224, "0x1015", "0xD195"), "in")
    steps = []
    for sequence in range(225, 245, 2):
        write = transaction(rows, sequence, "0x1016", "0xD195", None)
        steps.append({"writeSequence": sequence, "writtenUnsigned": scalar(write, "out"), "response": write["response"],
                      "readSequence": sequence + 1,
                      "readbackUnsigned": scalar(transaction(rows, sequence + 1, "0x1015", "0xD195"), "in")})
    if [(step["writtenUnsigned"], step["response"], step["readbackUnsigned"]) for step in steps] != PROBE:
        raise ValueError("grain probe differs from the reviewed run")
    client_probe = [test["grainProbe"] for test in records["guidedTests"] if "grainProbe" in test][0]
    if [(step["writtenUnsigned"], step["result"] == "refused") for step in client_probe["steps"]] != \
            [(written, response != "0x2001") for written, response, _ in PROBE]:
        raise ValueError("the client's grain probe record disagrees with the trace")
    comparisons = [test for test in records["guidedTests"] if test.get("bankComparisons")][0]["bankComparisons"]
    if [(entry["bank"], entry["verdict"], len(entry["rows"])) for entry in comparisons] != \
            [(bank, "matches", 12) for bank in range(1, 7)]:
        raise ValueError("expected all six banks compared, 12 rows each, with no differences")
    return {"firmwareReported": "2.13", "bankPass": banks,
            "bankSevenSelect": {"writeSequence": 164, "valueUnsigned": 7, "response": "0x200A",
                                "nextSelect": {"writeSequence": 165, "valueUnsigned": 1, "response": "0x2001"}},
            "grainProbe": {"bank": 1, "selectSequence": 223, "readBeforeSequence": 224, "valueBeforeUnsigned": before,
                           "steps": steps, "refusedWrites": [0, 6, 7, 8],
                           "offReconstructions": [{"writtenFirst": 2, "thenWritten": 1, "readbackUnsigned": 6},
                                                  {"writtenFirst": 5, "thenWritten": 1, "readbackUnsigned": 7}]},
            "menuComparison": {"basis": "the client's guided-test record; the owner compared each row with the camera's menu",
                               "checkedUtc": [entry["checkedUtc"] for entry in comparisons],
                               "banks": 6, "rowsPerBank": 12, "differences": 0},
            "notEstablished": ["USB mode", "AUTO UPDATE CUSTOM SETTING, ISO, lens and image format",
                               "menu readings beyond the client's comparison rows"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
