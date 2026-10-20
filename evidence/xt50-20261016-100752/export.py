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

SPEC = {"evidenceId": "xt50-20261016-100752",
        "sourceSha256": "176a885cc91f476decedb6fe4e94ba3df5055c4caee13df8d639adf8df119532",
        "imageFormat": "unknown"}


def build_findings(original):
    detail = original["findings"][0]["detail"]
    before = integer(detail["original"], 0xFFFF)
    expected = integer(detail["wrote"], 0xFFFF)
    after = integer(detail["value_after"], 0xFFFF)
    observed_trial = write_trial(original, 35, 36)
    if (scalar(original, 15, "0xD192") != before or
            observed_trial["writtenUnsigned"] != expected or
            scalar(original, 48, "0xD192") != after):
        raise ValueError("source finding and ledger disagree")
    return {"sourceFindingIndex": 0, "test": "power_dot", "selectedBank": 7,
            "initialReadSourceIndex": 15, "beforeUnsigned": before,
            "expectedUnsigned": expected, "trial": observed_trial,
            "nameWrite": name_comparison(original, 37),
            "afterReadSourceIndex": 48, "afterReadResponse": response(original, 48),
            "afterUnsigned": after,
            "procedureSource": {
                "artifact": "transcripts/bankprobe-20261016-100752.txt",
                "sha256": "b784bb15a799cd897a1a443e60e7185ad17938eb4e8966b75dd9f6cb1f486563",
                "archivePath": "hardware-runs/bankprobe-x-t50-2026-10-15/transcripts/bankprobe-20261016-100752.txt",
                "basis": "reviewed_pinned_private_transcript", "includedInPackage": False},
            "procedure": {"transcriptLines": [42, 50],
                          "itemEntryInstruction": "do_not_enter",
                          "itemEntryActuallyPerformed": "not_explicitly_reported",
                          "powerSequence": "off_wait_on", "instructedWaitSeconds": 5,
                          "completionBasis": "instruction_and_operator_continuation",
                          "independentPowerTelemetry": False},
            "operatorObservations": [
                {"basis": "reviewed_original_operator_response",
                 "sourcePointer": "/findings/0/detail/before", "stage": "before_power_instruction",
                 "redDot": "present", "locationIndividuallyEstablished": False},
                {"basis": "reviewed_original_operator_response",
                 "sourcePointer": "/findings/0/detail/after", "stage": "after_power_instruction",
                 "redDot": "absent", "locationIndividuallyEstablished": False}],
            "finalCleanup": cleanup(original, 75, 77, 123)}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
