#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bankprobe_package import package_main, code, hex_integer, EMPTY_NAME_PAYLOADS

SPEC = {"evidenceId": "xt50-20261019-102738",
        "sourceSha256": "fa0318589a7caa4b7d6e461da9649e519b36eea4f2b9101043d804f917fc2dc0",
        "sourceRevision": "c2e865e72c451688851a4c6706739a018c524f7a",
        "sourceDirectory": "hardware-runs/bankprobe-x-t50-2026-10-19",
        "imageFormat": "unknown"}


def response(original, index):
    value = original["transactions"][index].get("response")
    return None if value is None else code(hex_integer(value))


def name_payload(original, index, direction):
    row = original["transactions"][index]
    expected_op = "0x1015" if direction == "data_in" else "0x1016"
    if row["op"] != expected_op or row["params"] != ["0xD18D"]:
        raise ValueError("unexpected reviewed name row")
    return row[direction].lower()


def build_findings(original):
    rows = original["transactions"]
    if original.get("findings") is not None or len(rows) != 39:
        raise ValueError("source shape differs from the reviewed run")
    if rows[3]["params"] != ["0xD18C"] or rows[3]["data_out"] != "0700":
        raise ValueError("expected bank 7 selected before the name write")
    initial = name_payload(original, 5, "data_in")
    written = name_payload(original, 32, "data_out")
    readbacks = [name_payload(original, index, "data_in") for index in (33, 34)]
    if initial in EMPTY_NAME_PAYLOADS or written != "00" or readbacks != ["010000", "010000"]:
        raise ValueError("source finding and ledger disagree")
    if any(row.get("op") == "0x1016" and row.get("params") not in (["0xD18C"], ["0xD18D"]) for row in rows):
        raise ValueError("the reviewed run wrote no bank setting")
    return {"test": "empty_name_write", "selectedBank": 7,
            "initialName": {"readSourceIndex": 5, "readResponse": response(original, 5),
                            "wasEmpty": False, "contentsOmitted": True},
            "write": {"property": "0xD18D", "writeSourceIndex": 32, "payloadHex": written,
                      "payloadForm": "one_byte_empty_string", "response": response(original, 32)},
            "readbacks": [{"readSourceIndex": index, "readResponse": response(original, index),
                           "payloadHex": payload, "payloadForm": "count_one_and_nul",
                           "equalsWrittenBytes": payload == written}
                          for index, payload in zip((33, 34), readbacks)],
            "bankSettingsWritten": False, "nameRestoredByProbe": False,
            "selectorRestoredEventSourceIndex": 37,
            "closeSession": {"sourceIndex": 38, "response": response(original, 38)},
            "menuObservation": {"basis": "maintainer_report_after_run", "recordedIn": "maintainer_message",
                                "date": "2026-10-19", "bankLabel": "CUSTOM 7", "nameEditor": "blank",
                                "photograph": False},
            "persistenceAcrossPowerCycle": "not_tested"}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
