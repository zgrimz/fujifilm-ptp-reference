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

SPEC = {"evidenceId": "xt50-20261016-095611",
        "sourceSha256": "fafde86c62e91efc75cea8f91d66f29205a899454a5c5618c21ae0cceb847ddb",
        "imageFormat": "unknown"}


def build_findings(original):
    detail = original["findings"][0]["detail"]
    stages = []
    for stage_id, bi, wi, ri, ai, line in [
        ("R", 42, 62, 63, 78, 43), ("N", 78, 98, 99, 115, 54),
        ("V", 115, 135, 136, 151, 64),
    ]:
        source = detail[stage_id]
        before = integer(source["before"], 0xFFFF)
        expected = integer(source["wrote"], 0xFFFF)
        after = integer(source["after"], 0xFFFF)
        observed_trial = write_trial(original, wi, ri)
        if (scalar(original, bi, "0xD192") != before or
                observed_trial["writtenUnsigned"] != expected or
                scalar(original, ai, "0xD192") != after):
            raise ValueError("source finding and ledger disagree")
        stage = {"stage": stage_id, "beforeReadSourceIndex": bi,
                 "beforeUnsigned": before, "expectedUnsigned": expected,
                 "trial": observed_trial, "afterReadSourceIndex": ai,
                 "afterReadResponse": response(original, ai), "afterUnsigned": after,
                 "procedure": {"basis": "reviewed_pinned_private_transcript",
                               "line": line,
                               "itemEntryInstruction": "enter_and_leave_unchanged" if stage_id == "V" else "do_not_enter",
                               "resetInstruction": "perform_if_available" if stage_id == "V" else "perform"},
                 "operatorObservation": {"basis": "reviewed_original_operator_response",
                                         "sourcePointer": "/findings/0/detail/" + stage_id + "/seen",
                                         "redDotInitially": "present",
                                         "itemEntryReported": "entered_and_backed_out" if stage_id == "V" else "not_explicitly_reported",
                                         "redDotAfterItemExit": "absent" if stage_id == "V" else "not_applicable",
                                         "resetAvailable": "reported_unavailable" if stage_id == "V" else "reported_available",
                                         "resetAction": "not_performed_unavailable" if stage_id == "V" else "reported_performed",
                                         "saveAvailableAfterItemExit": "reported_unavailable" if stage_id == "V" else "not_reported"},
                 "nameWriteSourceIndex": 100 if stage_id == "N" else None}
        if stage_id == "N":
            stage["nameWrite"] = name_comparison(original, 100)
        stages.append(stage)
    return {"sourceFindingIndex": 0, "test": "reset_check", "selectedBank": 7,
            "startFilmSimulationUnsigned": integer(detail["start_sim"], 0xFFFF),
            "initialReadSourceIndex": 15,
            "procedureSource": {
                "artifact": "transcripts/bankprobe-20261016-095611.txt",
                "sha256": "631b7b9b4971567d29d934622097b2423e7bca277feb60cbaf9dc57cfa24ed95",
                "archivePath": "hardware-runs/bankprobe-x-t50-2026-10-15/transcripts/bankprobe-20261016-095611.txt",
                "basis": "reviewed_pinned_private_transcript", "includedInPackage": False},
            "stages": stages,
            "finalCleanup": cleanup(original, 171, 173, 219)}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
