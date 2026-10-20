#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client_report_package import package_main, EMPTY_NAME_PAYLOADS  # noqa: E402

SPEC = {"evidenceId": "xt50-20261019-140542",
        "sourceSha256": "23a8d14188add4d699bcd614d492a2775078a1637fb2f88d94339d864e316430",
        "sourceRevision": "50dabec6c251f39d30a6c962daafd4c71c7bde7d",
        "sourcePath": "hardware-runs/app-reports-x-t50/camera-reports/fuji-cookbook-camera-report-X-T50-20261019-1405.json",
        "imageFormat": "unknown"}

BANK = ["0x%04X" % value for value in range(0xD18E, 0xD1A5)]
SLOT_WALK_NAME = 161
PUSH_SELECT, UNDO_SELECT = 186, 256


def row(rows, sequence, operation, prop):
    entry = rows[sequence]
    if entry["operation"] != operation or entry["parameters"] != [prop] or entry.get("response") != "0x2001":
        raise ValueError("unexpected reviewed row %d" % sequence)
    return entry


def name_read(rows, sequence):
    entry = row(rows, sequence, "0x1015", "0xD18D")
    payload = entry.get("inData")
    if not isinstance(payload, str) or entry.get("inDataLength") != len(payload) // 2:
        raise ValueError("a reviewed name read lacks its complete bytes")
    return payload.lower()


def slot_write(rows, select):
    """Check one push-shaped write of C7 starting at its selector write; return its landmarks."""
    if row(rows, select, "0x1016", "0xD18C").get("outData") != "0700" or \
            row(rows, select + 1, "0x1015", "0xD18C").get("inData") != "0700":
        raise ValueError("expected C7 selected and read back")
    base = range(select + 2, select + 25)
    if [row(rows, s, "0x1015", rows[s]["parameters"][0])["parameters"][0] for s in base] != BANK:
        raise ValueError("expected the 23 bank settings read before the name")
    before, write = select + 25, select + 26
    row(rows, write, "0x1016", "0xD18D")
    sequence, written = write + 1, {}
    while rows[sequence]["operation"] == "0x1016":
        entry = row(rows, sequence, "0x1016", rows[sequence]["parameters"][0])
        if entry["parameters"][0] not in BANK:
            raise ValueError("expected only bank-setting writes after the name")
        written[entry["parameters"][0]] = entry["outData"]
        sequence += 1
    readback = {row(rows, s, "0x1015", rows[s]["parameters"][0])["parameters"][0]: rows[s]["inData"]
                for s in range(sequence, sequence + 23)}
    if list(readback) != BANK or any(readback[c] != v for c, v in written.items()):
        raise ValueError("expected every written setting read back equal")
    after = sequence + 23
    if any(rows[s]["parameters"] in (["0xD18C"], ["0xD18D"]) for s in range(write + 1, after)):
        raise ValueError("expected no selector change or name read inside the write")
    return {"before": before, "write": write, "writes": (write + 1, sequence - 1, len(written)),
            "readback": (sequence, sequence + 22), "after": after}


def record(original, at, kind):
    matches = [push for push in original["pushes"] if push["at"] == at and push["slot"] == 7 and push.get("kind") == kind]
    if len(matches) != 1:
        raise ValueError("expected one reviewed push record")
    return matches[0]


def build_findings(original):
    rows = {entry["sequence"]: entry for entry in original["transactions"]}
    if len(rows) != 325:
        raise ValueError("source shape differs from the reviewed run")
    if rows[SLOT_WALK_NAME - 2].get("outData") != "0700" or name_read(rows, SLOT_WALK_NAME) != "010000":
        raise ValueError("expected C7 unnamed at the slot walk")
    push, undo = slot_write(rows, PUSH_SELECT), slot_write(rows, UNDO_SELECT)
    if undo["after"] != 325 or push["after"] >= UNDO_SELECT:
        raise ValueError("source shape differs from the reviewed run")
    pushed_name = name_read(rows, push["after"])
    if name_read(rows, push["before"]) != "010000" or pushed_name in EMPTY_NAME_PAYLOADS:
        raise ValueError("expected the push to name an unnamed C7")
    if rows[push["write"]].get("outData") is not None or name_read(rows, undo["before"]) != pushed_name:
        raise ValueError("expected the undo to start from the pushed name")
    undo_write = rows[undo["write"]]
    if undo_write.get("outData") != "010000" or undo_write.get("outDataLength") != 3:
        raise ValueError("expected the three-byte empty name")
    final = name_read(rows, undo["after"])
    pushed = record(original, "2026-10-19T18:06:03Z", None)
    restored = record(original, "2026-10-19T18:06:14Z", "restore")
    if (pushed["nameBefore"], pushed["nameOutcome"], pushed["outcome"]) != ("", "written", "applied"):
        raise ValueError("expected the push record over an unnamed C7")
    if (restored["nameApplied"], restored["nameOutcome"], restored["outcome"]) != ("", "written", "applied"):
        raise ValueError("expected the restore record's verified empty name")
    first, last, count = undo["writes"]
    return {"test": "client_undo_empty_name", "selectedBank": 7,
            "nameAtSlotWalk": {"readSequence": SLOT_WALK_NAME, "payloadHex": "010000"},
            "push": {"selectSequence": PUSH_SELECT, "nameBeforeReadSequence": push["before"],
                     "nameBeforePayloadHex": "010000", "nameWriteSequence": push["write"],
                     "nameWriteNonEmpty": True, "settingWrites": push["writes"][2],
                     "nameAfterReadSequence": push["after"], "nameAfterNonEmpty": True, "contentsOmitted": True},
            "undo": {"selectSequence": UNDO_SELECT, "nameBeforeReadSequence": undo["before"],
                     "nameBeforeEqualsPushedNameBytes": True,
                     "nameWrite": {"property": "0xD18D", "writeSequence": undo["write"], "payloadHex": "010000",
                                   "payloadForm": "count_one_and_nul", "dataPhaseBytesHandedToTransport": 3,
                                   "response": "0x2001"},
                     "settingWritesAfterName": {"firstSequence": first, "lastSequence": last, "count": count,
                                                "allResponses": "0x2001",
                                                "readbackSequences": list(undo["readback"]),
                                                "allWrittenValuesReadBackEqual": True},
                     "nameReadsBetweenWriteAndFinalRead": 0,
                     "nameAfterWrites": {"readSequence": undo["after"], "payloadHex": final,
                                         "isEmptyForm": final in EMPTY_NAME_PAYLOADS}},
            "clientRecords": {
                "basis": "the client's push records in the same report",
                "pushToC7": {"recordedUtc": pushed["at"], "nameReadBeforeWasEmpty": True, "nameOutcome": "written",
                             "outcome": "applied"},
                "undoOfC7": {"recordedUtc": restored["at"], "nameApplied": "empty", "nameOutcome": "written",
                             "outcome": "applied"}},
            "notEstablished": ["the bytes ImageCaptureCore put on the USB wire",
                               "the name between the empty-name write and the final read",
                               "AUTO UPDATE CUSTOM SETTING, USB mode, ISO, lens and image format",
                               "persistence across a power cycle"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
