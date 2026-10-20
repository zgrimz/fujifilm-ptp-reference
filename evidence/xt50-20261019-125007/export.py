#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_report_package import package_main, EMPTY_NAME_PAYLOADS  # noqa: E402

SPEC = {"evidenceId": "xt50-20261019-125007",
        "sourceSha256": "905ec32db38047acff668b141c5fde1cf055f861438b43d330a1ec5d89b7c800",
        "sourceRevision": "2a3d1221d130e8d7cddf02f9f746dfe8adfa147b",
        "sourcePath": "hardware-runs/app-reports-x-t50/camera-reports/fuji-cookbook-camera-report-X-T50-20261019-1250.json",
        "imageFormat": "unknown"}

BANK = ["0x%04X" % value for value in range(0xD18E, 0xD1A5)]
SELECT, READ_ALL, NAME_READ, NAME_WRITE = 269, range(271, 294), 294, 295
WRITES, READBACK, FINAL_NAME_READ = range(296, 316), range(316, 339), 339


def row(rows, sequence, operation, prop):
    entry = rows[sequence]
    if entry["operation"] != operation or entry["parameters"] != [prop] or entry.get("response") != "0x2001":
        raise ValueError("unexpected reviewed row %d" % sequence)
    return entry


def name_bytes(entry):
    payload = entry.get("inData")
    if not isinstance(payload, str) or entry.get("inDataLength") != len(payload) // 2:
        raise ValueError("a reviewed name read lacks its complete bytes")
    return payload.lower()


def push_record(original, at):
    matches = [push for push in original["pushes"] if push["at"] == at and push["slot"] == 7]
    if len(matches) != 1:
        raise ValueError("expected one reviewed push record")
    return matches[0]


def build_findings(original):
    rows = {entry["sequence"]: entry for entry in original["transactions"]}
    if len(rows) != 339:
        raise ValueError("source shape differs from the reviewed run")
    if row(rows, SELECT, "0x1016", "0xD18C").get("outData") != "0700" or \
            row(rows, SELECT + 1, "0x1015", "0xD18C").get("inData") != "0700":
        raise ValueError("expected C7 selected and read back before the restore")
    if any(rows[s]["parameters"] == ["0xD18C"] for s in range(SELECT + 2, FINAL_NAME_READ + 1)):
        raise ValueError("the reviewed restore selects no other bank")
    if [row(rows, s, "0x1015", rows[s]["parameters"][0])["parameters"][0] for s in READ_ALL] != BANK:
        raise ValueError("expected the 23 bank settings read before the name")
    before = name_bytes(row(rows, NAME_READ, "0x1015", "0xD18D"))
    write = row(rows, NAME_WRITE, "0x1016", "0xD18D")
    if before in EMPTY_NAME_PAYLOADS or write.get("outData") != "00" or write.get("outDataLength") != 1:
        raise ValueError("expected a named bank and the one-byte empty name write")
    written = {}
    for s in WRITES:
        entry = rows[s]
        if entry["operation"] != "0x1016" or entry["parameters"][0] not in BANK or entry.get("response") != "0x2001":
            raise ValueError("expected 20 accepted bank-setting writes after the name")
        written[entry["parameters"][0]] = entry["outData"]
    readback = {row(rows, s, "0x1015", rows[s]["parameters"][0])["parameters"][0]: rows[s]["inData"] for s in READBACK}
    if len(written) != 20 or list(readback) != BANK or any(readback[c] != v for c, v in written.items()):
        raise ValueError("expected every written setting read back equal")
    after = name_bytes(row(rows, FINAL_NAME_READ, "0x1015", "0xD18D"))
    if any(rows[s]["parameters"] == ["0xD18D"] for s in range(NAME_WRITE + 1, FINAL_NAME_READ)):
        raise ValueError("the reviewed restore reads the name only at the end")
    pushed, restored = push_record(original, "2026-10-19T16:48:27Z"), push_record(original, "2026-10-19T16:50:47Z")
    if pushed["nameBefore"] != "" or pushed["nameOutcome"] != "written" or not pushed["nameApplied"]:
        raise ValueError("expected the push over an unnamed C7 with its name verified")
    if (restored.get("kind"), restored["nameApplied"], restored["nameOutcome"], restored["outcome"]) != \
            ("restore", "", "mismatched", "partiallyApplied"):
        raise ValueError("expected the restore record's name mismatch")
    return {"test": "client_restore_empty_name", "selectedBank": 7,
            "selection": {"writeSequence": SELECT, "readSequence": SELECT + 1, "selectedUnsigned": 7},
            "nameBeforeWrite": {"readSequence": NAME_READ, "readResponse": "0x2001", "wasEmpty": False,
                                "contentsOmitted": True},
            "nameWrite": {"property": "0xD18D", "writeSequence": NAME_WRITE, "payloadHex": "00",
                          "payloadForm": "one_byte_empty_string", "dataPhaseBytesHandedToTransport": 1,
                          "response": "0x2001"},
            "settingWritesAfterName": {"firstSequence": WRITES.start, "lastSequence": WRITES.stop - 1,
                                       "count": len(written), "properties": sorted(written),
                                       "allResponses": "0x2001",
                                       "readbackSequences": [READBACK.start, READBACK.stop - 1],
                                       "allWrittenValuesReadBackEqual": True},
            "nameReadsBetweenWriteAndFinalRead": 0,
            "nameAfterWrites": {"readSequence": FINAL_NAME_READ, "readResponse": "0x2001",
                                "isEmptyForm": after in EMPTY_NAME_PAYLOADS,
                                "equalsNameBeforeWriteBytes": after == before, "contentsOmitted": True},
            "clientRecords": {
                "basis": "the client's push records in the same report; their own transactions precede this trace",
                "pushToC7": {"recordedUtc": pushed["at"], "nameReadBeforeWasEmpty": True,
                             "pushedNameNonEmpty": True, "nameOutcome": "written"},
                "restoreOfC7": {"recordedUtc": restored["at"], "nameApplied": "empty", "nameOutcome": "mismatched",
                                "outcome": "partiallyApplied"}},
            "notEstablished": ["the bytes ImageCaptureCore put on the USB wire",
                               "the name between the empty-name write and the final read",
                               "AUTO UPDATE CUSTOM SETTING, USB mode, ISO, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
