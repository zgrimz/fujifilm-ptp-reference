#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bankprobe_package import package_main, code  # noqa: E402

SPEC = {"evidenceId": "xt50-20261019-133848",
        "sourceSha256": "e53af100187c140dd8654b60f7e21fab8e9044404fb834e2d9e2cd26a4bc1112",
        "sourceRevision": "1d491480ea2e108d45f9e9d0eea0d241ee750e13",
        "sourceDirectory": "hardware-runs/bankprobe-x-t50-2026-10-19",
        "imageFormat": "unknown"}

INITIAL_NAME_READ = 34
# Per form: name write, its read, setting write/read, name read, setting write-back/read, name read,
# original-name write, its read.
TRIALS = (("00", "one_byte_empty_string", 59), ("010000", "count_one_and_nul", 73))
SIMULATION, TEMPORARY = 11, 2
VERIFICATION, CLOSE = 140, 144


def row(rows, index, op, prop):
    entry = rows[index]
    if entry.get("op") != op or entry.get("params") != [prop] or entry.get("response") != "0x2001":
        raise ValueError("unexpected reviewed row %d" % index)
    return entry


def name_payload(rows, index, op):
    return row(rows, index, op, "0xD18D")["data_in" if op == "0x1015" else "data_out"].lower()


def setting(rows, index, op):
    entry = row(rows, index, op, "0xD192")
    return int.from_bytes(bytes.fromhex(entry["data_in" if op == "0x1015" else "data_out"]), "little")


def trial(rows, payload, form, start, initial):
    if name_payload(rows, start, "0x1016") != payload:
        raise ValueError("unexpected empty-name write")
    reads = [name_payload(rows, index, "0x1015") for index in (start + 1, start + 5, start + 9)]
    temporary = (setting(rows, start + 3, "0x1016"), setting(rows, start + 4, "0x1015"))
    back = (setting(rows, start + 7, "0x1016"), setting(rows, start + 8, "0x1015"))
    if reads != ["010000"] * 3 or temporary != (TEMPORARY, TEMPORARY) or back != (SIMULATION, SIMULATION):
        raise ValueError("source finding and ledger disagree")
    restored = (name_payload(rows, start + 11, "0x1016"), name_payload(rows, start + 12, "0x1015"))
    if restored != (initial, initial):
        raise ValueError("expected the original name written and read back")
    return {"form": form, "payloadHex": payload, "writeSourceIndex": start, "response": "0x2001",
            "readbacks": [
                {"after": "name_write", "readSourceIndex": start + 1, "payloadHex": reads[0]},
                {"after": "setting_write", "settingWriteSourceIndex": start + 3, "settingReadbackUnsigned": TEMPORARY,
                 "readSourceIndex": start + 5, "payloadHex": reads[1]},
                {"after": "setting_write_back", "settingWriteSourceIndex": start + 7,
                 "settingReadbackUnsigned": SIMULATION, "readSourceIndex": start + 9, "payloadHex": reads[2]}],
            "originalNameRestore": {"writeSourceIndex": start + 11, "readSourceIndex": start + 12,
                                    "response": "0x2001", "readEqualsInitialNameBytes": True}}


def build_findings(original):
    rows = original["transactions"]
    findings = original.get("findings") or []
    if len(rows) != 145 or len(findings) != 1 or findings[0]["test"] != "empty-name":
        raise ValueError("source shape differs from the reviewed run")
    detail = findings[0]["detail"]
    if detail["bank"] != 7 or detail["setting"] != "0xD192" or detail["setting_values"] != [SIMULATION, TEMPORARY]:
        raise ValueError("source finding differs from the reviewed run")
    if rows[2].get("event") != "experiment context" or rows[2]["auto_update"] != "unknown":
        raise ValueError("expected the recorded experiment context")
    initial = name_payload(rows, INITIAL_NAME_READ, "0x1015")
    if initial in ("00", "010000") or setting(rows, 39, "0x1015") != SIMULATION:
        raise ValueError("expected a named C7 holding Classic Chrome")
    writes = [entry for entry in rows if entry.get("op") == "0x1016" and entry["params"] not in (["0xD18C"], ["0xD18D"], ["0xD192"])]
    if writes:
        raise ValueError("the reviewed run wrote no other bank setting")
    verification = rows[VERIFICATION]
    if verification.get("event") != "bank restore verification" or verification["exact"] is not True or verification["writes"]:
        raise ValueError("expected an exact cleanup that needed no writes")
    if rows[CLOSE].get("op") != "0x1003" or rows[CLOSE].get("response") != "0x2001":
        raise ValueError("expected a closed session")
    return {"test": "empty_name_with_setting_writes", "selectedBank": 7,
            "initialName": {"readSourceIndex": INITIAL_NAME_READ, "readResponse": "0x2001", "wasEmpty": False,
                            "contentsOmitted": True},
            "settingWritten": code(0xD192), "settingOriginalUnsigned": SIMULATION,
            "settingTemporaryUnsigned": TEMPORARY,
            "trials": [trial(rows, payload, form, start, initial) for payload, form, start in TRIALS],
            "cleanup": {"verificationSourceIndex": VERIFICATION, "exact": True, "cleanupWrites": 0},
            "autoUpdateReported": "unknown",
            "closeSession": {"sourceIndex": CLOSE, "response": "0x2001"},
            "persistenceAcrossPowerCycle": "not_tested"}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
