#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export only this hash-pinned private run; never copy the original into the repo.

This companion format deliberately does not claim report.schema.json compliance:
the source has no per-transaction timestamps or reliable connection identifiers.
"""

import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys


SOURCE_SHA256 = "cd14cc1d2fee70b7d19706cdc4e5a47e39008c365d475aba42bfb9e054f6b28c"
SOURCE_REVISION = "803067ca4b4aefaf9849e4bda0209317a9ff2582"
SOURCE_PATH = "hardware-runs/bankprobe-x-t50-2026-10-15/logs/bankprobe-20261015-224819.json"
EVIDENCE_ID = "xt50-20261015-224819"
BANK_CODES = frozenset(range(0xD18E, 0xD1A5))
SCALAR_CODES = BANK_CODES | {0xD18C, 0xD1A5}
OPCODES = {0x1001, 0x1002, 0x1003, 0x1015, 0x1016}
EVENTS = {"camera lost; waiting for it": "camera_lost", "camera back": "camera_back"}
HEX = re.compile(r"0x[0-9a-fA-F]{1,8}\Z")
RAW = re.compile(r"(?:[0-9a-fA-F]{2}){1,4}\Z")
LOCAL_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\Z")


def integer(value, maximum=0xFFFFFFFF):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("expected a bounded unsigned integer")
    return value


def hex_integer(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("expected a bounded hexadecimal integer")
    return int(value, 16)


def code(value):
    return "0x%04X" % integer(value, 0xFFFF)


def local_time(value):
    if not isinstance(value, str) or not LOCAL_TIME.fullmatch(value):
        raise ValueError("expected an unoffset local timestamp")
    datetime.datetime.fromisoformat(value)
    return value


def raw_scalar(value):
    if not isinstance(value, str) or not RAW.fullmatch(value):
        raise ValueError("scalar payload must contain one to four bytes")
    return value.lower()


def ledger_rows(rows):
    """Construct a fresh allowlisted row; no source dictionary is copied."""
    result = []
    for source_index, original in enumerate(rows):
        row = {"sourceIndex": source_index}
        if "event" in original:
            row.update(kind="event", event=EVENTS[original["event"]],
                       recordedLocalTime=local_time(original["at"]))
        else:
            opcode = hex_integer(original["op"])
            if opcode not in OPCODES:
                raise ValueError("unsupported opcode")
            params = [hex_integer(value) for value in original["params"]]
            expected_count = 1 if opcode in (0x1002, 0x1015, 0x1016) else 0
            if len(params) != expected_count:
                raise ValueError("unexpected parameter count")
            response = (hex_integer(original["response"])
                        if "response" in original else None)
            row.update(kind="transaction", transactionId=integer(original["tid"]),
                       opcode=code(opcode), parameters=params,
                       response=code(response) if response is not None else None,
                       outcome=("recorded_ok" if response == 0x2001 else
                                "recorded_refusal" if response is not None else
                                "outcome_unknown"),
                       transportErrorRecorded="usb_error" in original)
            prop = params[0] if opcode in (0x1015, 0x1016) else None
            for source_key, target_key in (("data_in", "dataInLE"), ("data_out", "dataOutLE")):
                if source_key not in original:
                    continue
                if prop in SCALAR_CODES:
                    row[target_key] = raw_scalar(original[source_key])
                else:
                    # Even a short name/identity payload is never a scalar.
                    row.setdefault("omittedPayloads", []).append(source_key)
        result.append(row)
    return result


def snapshot_rows(rows):
    result = []
    for source_index, original in enumerate(rows):
        bank_settings, live_settings, refused = {}, {}, {}
        for source_key, value in original["props"].items():
            prop = hex_integer(source_key)
            if prop not in BANK_CODES | {0xD1A5}:
                raise ValueError("unexpected snapshot property")
            target = bank_settings if prop in BANK_CODES else live_settings
            target[code(prop)] = hex_integer(value) if value is not None else None
        for source_key, value in original["refused"].items():
            prop = hex_integer(source_key)
            if prop not in BANK_CODES | {0xD1A5}:
                raise ValueError("unexpected refused snapshot property")
            refused[code(prop)] = integer(value, 0xFFFF) if type(value) is int else hex_integer(value)
        result.append({"sourceSnapshotIndex": source_index,
                       "selectedBank": integer(original["bank"], 7),
                       "recordedLocalTime": local_time(original["taken"]),
                       "bankSettingsUnsigned": bank_settings,
                       "liveSettingsUnsigned": live_settings,
                       "refusedResponses": refused})
    return result


def trial(original):
    prop = integer(original["code"], 0xFFFF)
    if prop not in SCALAR_CODES:
        raise ValueError("unexpected finding property")
    return {"property": code(prop), "writtenUnsigned": integer(original["wrote"], 0xFFFF),
            "response": code(integer(original["rc"], 0xFFFF)),
            "readbackUnsigned": (integer(original["read"], 0xFFFF)
                                 if original["read"] is not None else None)}


def numeric_findings(findings):
    """Keep typed observations and fixed labels, not source prose/verdicts/ok flags."""
    expected_tests = ["filmsim", "d1a3", "dr-placeholder", "selector", "dr-zero",
                      "toning", "mono-colour", "heif", "d1a5-write", "name-last"]
    if [item["test"] for item in findings] != expected_tests:
        raise ValueError("unexpected finding order")
    labels = ["PRO Neg. Hi", "PRO Neg. Std", "MONOCHROME", "MONOCHROME + Ye", "SEPIA",
              "ACROS", "ACROS + Ye", "ACROS + R", "ACROS + G"]
    menu_rows = findings[0]["detail"]
    if len(menu_rows) != len(labels):
        raise ValueError("unexpected film-simulation observation count")
    film_sim = []
    for index, (original, label) in enumerate(zip(menu_rows, labels)):
        if original["menu"] != label or original["others_changed"] != []:
            raise ValueError("film-simulation observation needs renewed review")
        film_sim.append({"sourceDetailIndex": index, "promptedMenuLabel": label,
                         "readUnsigned": integer(original["value"], 0xFFFF),
                         "expectedUnsigned": integer(original["expected"], 0xFFFF),
                         "reportedOtherChanges": 0})
    menu_changes = []
    prompt_labels = ["LMO toggle", "Long Exposure NR toggle", "Color Space toggle", "Color Space return"]
    if len(findings[1]["detail"]) != len(prompt_labels):
        raise ValueError("unexpected menu-mapping count")
    for index, (original, label) in enumerate(zip(findings[1]["detail"], prompt_labels)):
        changes = []
        for prop, before, after in original["changed"]:
            prop_number = hex_integer(prop)
            if prop_number not in BANK_CODES:
                raise ValueError("unexpected menu-mapping property")
            changes.append({"property": code(prop_number), "beforeUnsigned": integer(before, 0xFFFF),
                            "afterUnsigned": integer(after, 0xFFFF)})
        menu_changes.append({"sourceDetailIndex": index, "promptLabel": label, "reportedChanges": changes})
    result = [
        {"sourceFindingIndex": 0, "kind": "prompted_film_simulation", "rows": film_sim},
        {"sourceFindingIndex": 1, "kind": "prompted_menu_mapping", "rows": menu_changes},
        {"sourceFindingIndex": 3, "kind": "selector_report",
         "values": {key: integer(findings[3]["detail"][key], 7)
                    for key in ("before", "selected", "after_cable", "after_menu")}},
    ]
    for index, kind in ((4, "dynamic_range_trials"), (5, "toning_trials"), (6, "monochrome_colour_trials")):
        result.append({"sourceFindingIndex": index, "kind": kind,
                       "rows": [{"sourceDetailIndex": row_index, **trial(row)}
                                for row_index, row in enumerate(findings[index]["detail"])]})
    heif = findings[7]["detail"]
    result.append({"sourceFindingIndex": 7, "kind": "prompted_format_trials",
                   "heif": [trial(row) for row in heif["heif"]],
                   "jpeg": [trial(row) for row in heif["jpeg"]],
                   "d18fHeifUnsigned": integer(heif["d18f_heif"], 0xFFFF),
                   "d18fJpegUnsigned": integer(heif["d18f_jpeg"], 0xFFFF)})
    result.append({"sourceFindingIndex": 8, "kind": "live_size_report",
                   "sourceNamedValues": {key: integer(findings[8]["detail"][key], 0xFFFF)
                                         for key in ("a5_k", "a5_j", "e_j", "target")}})
    return {"format": "fuji-bankprobe-selected-numeric-findings-v1", "evidenceId": EVIDENCE_ID,
            "sourceFindingCount": 10, "omittedSourceFindingIndices": [2, 9],
            "findings": result}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def export_bundle(original_bytes):
    if sha256(original_bytes) != SOURCE_SHA256:
        raise ValueError("original SHA-256 does not match the reviewed run")
    original = json.loads(original_bytes)
    if original["model"] != "X-T50" or original["firmware"] != "1.32":
        raise ValueError("unexpected source camera metadata")
    ledger = ledger_rows(original["transactions"])
    before = snapshot_rows(original["banks_before"])
    after = snapshot_rows(original["banks_after"])
    outputs = {
        "transactions.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8") for row in ledger),
        "snapshots.json": json_bytes({"format": "fuji-bankprobe-numeric-snapshots-v1", "evidenceId": EVIDENCE_ID,
                                      "before": before, "after": after}),
        "findings.json": json_bytes(numeric_findings(original["findings"])),
    }
    operations = [row for row in ledger if row["kind"] == "transaction"]
    events = [row for row in ledger if row["kind"] == "event"]
    scalar_payloads = sum(key in row for row in operations for key in ("dataInLE", "dataOutLE"))
    omitted_payloads = sum(len(row.get("omittedPayloads", [])) for row in operations)
    manifest = {
        "format": "fuji-bankprobe-sanitized-package-v1", "evidenceId": EVIDENCE_ID,
        "evidenceKind": "measured_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": SOURCE_PATH, "revision": SOURCE_REVISION,
                   "sha256": SOURCE_SHA256, "bytes": len(original_bytes), "toolRevision": None},
        "camera": {"model": "X-T50", "firmware": "1.32", "provenance": "original_report", "usbMode": None},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None,
                       "imageFormat": "varied_by_prompted_subtest"},
        "time": {"startedLocal": local_time(original["started"]), "timezone": None,
                 "perTransactionTimestamps": "absent", "connectionIds": "absent"},
        "coverage": {"sourceArray": "transactions", "sourceEntries": len(ledger),
                     "retainedEntries": len(ledger), "droppedEntries": 0,
                     "transactionEntries": len(operations), "eventEntries": len(events),
                     "outcomes": dict(sorted(collections.Counter(row["outcome"] for row in operations).items())),
                     "scalarPayloadsRetained": scalar_payloads, "payloadFieldsOmitted": omitted_payloads,
                     "beforeSnapshots": len(before), "afterSnapshots": len(after),
                     "sourceCaptureCompleteness": "unknown"},
        "interpretation": {"sourceIndex": "zero-based original transactions array index; order preserved",
                           "transactionId": "source value; repeats across sessions and is not a unique identifier",
                           "rawPayloadEncoding": "hexadecimal bytes in source order, little-endian scalar interpretation",
                           "snapshotAndFindingNumbers": "unsigned integers; not byte strings",
                           "responseOrigin": "not independently established by this host-generated log",
                           "events": "host-recorded camera_lost/camera_back; not proof of a power cycle",
                           "liveD1A5": "live setting sampled while a bank was selected, not a 24th bank field"},
        "transform": {"generator": "export.py", "generatorSha256": sha256(Path(__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False,
                      "losslessBackup": False,
                      "payloadAllowlist": [code(value) for value in sorted(SCALAR_CODES)],
                      "maximumPayloadBytes": 4,
                      "omissions": ["command line and paths", "bank names and all D18D payloads",
                                    "DeviceInfo and D186/D187 payloads", "identity and device identifiers",
                                    "USB error text", "source verdict prose and ok flags",
                                    "findings 2 and 9 containing interpretations not adopted by this package",
                                    "unrestricted source strings and unknown fields"],
                      "generatedFacts": "No times, connection identifiers, conditions, or hardware observations are invented."},
        "artifacts": {name: {"sha256": sha256(value), "bytes": len(value)} for name, value in outputs.items()},
    }
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="private original outside the repository")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true", help="compare the deterministic export without writing")
    args = parser.parse_args(argv)
    script = Path(__file__).resolve()
    repository = next((parent for parent in script.parents if (parent / ".git").exists()), script.parents[2])
    if args.original.resolve().is_relative_to(repository):
        parser.error("keep the original outside the repository")
    try:
        outputs = export_bundle(args.original.read_bytes())
        if args.check:
            for name, expected in outputs.items():
                if (args.output_dir / name).read_bytes() != expected:
                    raise ValueError("generated artifact differs: " + name)
            print("Verified original hash and all four deterministic artifacts.")
        else:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for name, value in outputs.items():
                (args.output_dir / name).write_bytes(value)
            print("Wrote four sanitized artifacts; original unchanged.")
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    sys.exit(main())
