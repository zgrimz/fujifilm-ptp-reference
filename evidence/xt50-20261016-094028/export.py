#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bankprobe_package import package_main, integer, hex_integer, code, raw_scalar


def scalar(original, index, prop, direction="data_in"):
    row = original["transactions"][index]
    expected_op = "0x1015" if direction == "data_in" else "0x1016"
    if row["op"] != expected_op or row["params"] != [prop]:
        raise ValueError("unexpected reviewed scalar row")
    return int.from_bytes(bytes.fromhex(raw_scalar(row[direction])), "little")


def response(original, index):
    value = original["transactions"][index].get("response")
    return None if value is None else code(hex_integer(value))


def write_trial(original, write_index, read_index, prop="0xD192"):
    return {"property": prop, "writeSourceIndex": write_index,
            "writtenUnsigned": scalar(original, write_index, prop, "data_out"),
            "response": response(original, write_index),
            "readSourceIndex": read_index,
            "readResponse": response(original, read_index),
            "readbackUnsigned": scalar(original, read_index, prop)}


def name_comparison(original, write_index, read_index=None):
    rows = original["transactions"]
    if rows[10]["params"] != ["0xD18D"] or rows[write_index]["params"] != ["0xD18D"]:
        raise ValueError("unexpected reviewed name row")
    initial = bytes.fromhex(rows[10]["data_in"])
    written = bytes.fromhex(rows[write_index]["data_out"])
    result = {"property": "0xD18D", "initialReadSourceIndex": 10,
              "writeSourceIndex": write_index, "response": response(original, write_index),
              "equalsInitialBytes": written == initial, "readSourceIndex": read_index,
              "readbackEqualsWrittenBytes": None}
    if read_index is not None:
        if rows[read_index]["params"] != ["0xD18D"]:
            raise ValueError("unexpected reviewed name read")
        result["readResponse"] = response(original, read_index)
        result["readbackEqualsWrittenBytes"] = bytes.fromhex(rows[read_index]["data_in"]) == written
    return result


def cleanup(original, start, first_name, final_name):
    initial = {original["transactions"][i]["params"][0]: i for i in range(11, 35)}
    pairs = []
    for i in range(start, final_name):
        row = original["transactions"][i]
        if row.get("op") != "0x1016" or len(row.get("params", [])) != 1:
            continue
        prop = row["params"][0]
        if prop not in initial:
            continue
        pair = write_trial(original, i, i + 1, prop)
        pair["scope"] = "live" if prop == "0xD1A5" else "bank"
        pair["initialReadSourceIndex"] = initial[prop]
        pair["initialUnsigned"] = scalar(original, initial[prop], prop)
        pairs.append(pair)
    return {"sourceBasis": "numeric_transaction_comparison",
            "numericWritesAndReadbacks": pairs,
            "bankPropertiesNotReadAfterCleanup": ["0xD19C", "0xD19F"],
            "initialNameRewrite": name_comparison(original, first_name, first_name + 1),
            "finalNameRewrite": name_comparison(original, final_name),
            "laterPersistenceCheck": "not_recorded",
            "closeSession": {"sourceIndex": final_name + 1,
                             "response": response(original, final_name + 1),
                             "transportErrorRecorded": "usb_error" in original["transactions"][final_name + 1]},
            "wholeBankExactRestorationEstablished": False}

SPEC = {"evidenceId": "xt50-20261016-094028",
        "sourceSha256": "96bf39bf6f5b696f902d2ab1e0e60ebb05bff9132fc4562863a04993419a63f8",
        "imageFormat": "unknown"}


def build_findings(original):
    detail = original["findings"][0]["detail"]
    stages = []
    reviewed = [
        ("1-same-session", "same_ptp_session_immediate", 35, 36, 37,
         "entered_and_backed_out", "absent", "reported_unavailable", 46, 47),
        ("2-wait-10s", "same_ptp_session_reported_delay", 45, 46, 47,
         "explicitly_not_entered", "not_applicable", "reported_performed", 49, 59),
        ("3-new-ptp-session", "new_ptp_session", 55, 56, 62,
         "not_reported", "not_reported", "reported_performed", 61, 72),
        ("4-reconnect", "cable_reconnect_instruction", 70, 71, 76,
         "not_reported", "not_reported", "reported_performed", 74, 86),
    ]
    for stage_id, condition, wi, ri, ni, entry, after, saved, first_line, last_line in reviewed:
        expected = integer(detail[stage_id]["wrote"], 0xFFFF)
        observed_trial = write_trial(original, wi, ri)
        if observed_trial["writtenUnsigned"] != expected:
            raise ValueError("source finding and ledger disagree")
        stage = {"stage": stage_id, "condition": condition,
                 "expectedUnsigned": expected, "trial": observed_trial,
                 "nameWrite": name_comparison(original, ni),
                 "operatorObservation": {
                     "basis": "reviewed_original_operator_response",
                     "sourcePointer": "/findings/0/detail/" + stage_id + "/seen",
                     "redDotBeforeSaving": "present",
                     "itemEntryBehavior": entry, "redDotAfterItemExit": after,
                     "saveAction": saved,
                     "filmSimulationLabelCorrespondsToUnsigned": expected},
                 "procedureTranscriptLines": [first_line, last_line]}
        if stage_id == "2-wait-10s":
            stage["delay"] = {"basis": "tool_transcript", "reportedSeconds": 10,
                              "independentlyMeasuredSeconds": None}
        if stage_id == "3-new-ptp-session":
            stage["sessionBoundary"] = {"closeSourceIndex": 57, "openSourceIndex": 59,
                                        "closeResponse": response(original, 57),
                                        "openResponse": response(original, 59)}
        if stage_id == "4-reconnect":
            stage["reconnect"] = {"basis": "instruction_and_operator_continuation",
                                  "instructedWaitSeconds": 5,
                                  "independentCableTelemetry": False}
        stages.append(stage)
    return {"sourceFindingIndex": 0, "test": "name_timing", "selectedBank": 7,
            "startFilmSimulationUnsigned": integer(detail["start_sim"], 0xFFFF),
            "initialReadSourceIndex": 15,
            "initialOperatorObservation": {"basis": "reviewed_original_operator_response",
                                           "sourcePointer": "/findings/0/detail/before_test",
                                           "redDot": "absent", "filmSimulationLabelCorrespondsToUnsigned": 12},
            "procedureSource": {
                "artifact": "transcripts/bankprobe-20261016-094028.txt",
                "sha256": "ff9c72dbc6a84dc82d941212a26570ca2986b60c33681e9ecc1be9efedf5d82b",
                "archivePath": "hardware-runs/bankprobe-x-t50-2026-10-15/transcripts/bankprobe-20261016-094028.txt",
                "basis": "reviewed_pinned_private_transcript", "includedInPackage": False},
            "stages": stages,
            "finalCleanup": cleanup(original, 84, 86, 132)}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
