#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted companion exports for individually reviewed, hash-pinned bankprobe runs.

Run-specific exporters select and normalize findings. This module preserves ordered
transaction evidence, optional numeric snapshots and immutable-source provenance.
It does not run camera operations or turn legacy logs into schema-v1 reports.
"""

import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

SOURCE_REVISION = "803067ca4b4aefaf9849e4bda0209317a9ff2582"
SOURCE_DIRECTORY = "hardware-runs/bankprobe-x-t50-2026-10-15"
# The two encodings of an empty bank name hold no name: the standard one-byte empty string, and
# the count-plus-NUL form the X-T50 answers for an unnamed bank. Every other 0xD18D payload is a name.
EMPTY_NAME_PAYLOADS = frozenset({"00", "010000"})

BANK_CODES = frozenset(range(0xD18E, 0xD1A5))
SCALAR_CODES = BANK_CODES | {0xD18C, 0xD1A5}
OPCODES = {0x1001, 0x1002, 0x1003, 0x1015, 0x1016}
EVENTS = {"camera lost; waiting for it": "camera_lost", "camera back": "camera_back",
          "selector restored": "selector_restored", "experiment context": "experiment_context",
          "bank restore verification": "bank_restore_verification"}
# An experiment context keeps only bankprobe's normalized AUTO UPDATE answer, never the operator's free
# text; a restore verification keeps each field's status, never the original or read value (one is the name).
AUTO_UPDATE_ANSWERS = frozenset({"on", "off", "unknown"})
CHECK_STATUSES = frozenset({"exact", "semantic-only", "mismatched", "unavailable"})
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
            row.update(kind="event", event=EVENTS[original["event"]])
            if "at" in original:
                row["recordedLocalTime"] = local_time(original["at"])
            if "value" in original:
                row["restoredSelector"] = integer(original["value"], 7)
            if original["event"] == "experiment context":
                if original["auto_update"] not in AUTO_UPDATE_ANSWERS:
                    raise ValueError("unexpected AUTO UPDATE answer")
                row.update(bank=integer(original["bank"], 7), autoUpdateReported=original["auto_update"])
            elif original["event"] == "bank restore verification":
                if type(original["exact"]) is not bool or any(c["status"] not in CHECK_STATUSES for c in original["checks"]):
                    raise ValueError("unexpected restore verification")
                row.update(bank=integer(original["bank"], 7), exact=original["exact"],
                           checkStatuses={code(integer(c["code"], 0xFFFF)): c["status"] for c in original["checks"]},
                           cleanupWrites=len(original["writes"]))
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
            for source_key, target_key, empty_key in (("data_in", "dataInLE", "emptyNameInHex"),
                                                      ("data_out", "dataOutLE", "emptyNameOutHex")):
                if source_key not in original:
                    continue
                payload = original[source_key]
                if prop in SCALAR_CODES:
                    row[target_key] = raw_scalar(payload)
                elif prop == 0xD18D and isinstance(payload, str) and payload.lower() in EMPTY_NAME_PAYLOADS:
                    row[empty_key] = payload.lower()
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


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def build_package(original_bytes, spec, build_findings, exporter_path):
    """Verify the reviewed source before any finding projection is invoked."""
    evidence_id = spec["evidenceId"]
    if not re.fullmatch(r"xt50-202610(?:15|16|19)-[0-9]{6}", evidence_id):
        raise ValueError("unexpected package identifier")
    source_revision = spec.get("sourceRevision", SOURCE_REVISION)
    source_directory = spec.get("sourceDirectory", SOURCE_DIRECTORY)
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision) or not re.fullmatch(r"hardware-runs/[a-z0-9-]+", source_directory):
        raise ValueError("invalid source revision or directory")
    if not re.fullmatch(r"[0-9a-f]{64}", spec["sourceSha256"]):
        raise ValueError("invalid source hash")
    if sha256(original_bytes) != spec["sourceSha256"]:
        raise ValueError("original SHA-256 does not match the reviewed run")
    original = json.loads(original_bytes)
    if original["model"] != "X-T50" or original["firmware"] != "1.32":
        raise ValueError("unexpected source camera metadata")
    ledger = ledger_rows(original["transactions"])
    outputs = {
        "transactions.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8") for row in ledger),
        "findings.json": json_bytes({"format": "fuji-bankprobe-selected-observations-v1", "evidenceId": evidence_id,
                                     "sourceFindingCount": len(original.get("findings") or []),
                                     "findings": build_findings(original)}),
    }
    if ("banks_before" in original) != ("banks_after" in original):
        raise ValueError("partial top-level snapshot pair requires separate review")
    before, after = [], []
    if "banks_before" in original:
        before = snapshot_rows(original["banks_before"])
        after = snapshot_rows(original["banks_after"])
        outputs["snapshots.json"] = json_bytes({"format": "fuji-bankprobe-numeric-snapshots-v1", "evidenceId": evidence_id,
                                               "before": before, "after": after})
    operations = [row for row in ledger if row["kind"] == "transaction"]
    source_name = "bankprobe-" + evidence_id.removeprefix("xt50-") + ".json"
    manifest = {
        "format": "fuji-bankprobe-sanitized-package-v1", "evidenceId": evidence_id,
        "evidenceKind": "measured_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": source_directory + "/logs/" + source_name,
                   "revision": source_revision, "sha256": spec["sourceSha256"], "bytes": len(original_bytes), "toolRevision": None},
        "camera": {"model": "X-T50", "firmware": "1.32", "provenance": "original_report", "usbMode": None},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None,
                       "imageFormat": spec.get("imageFormat", "unknown")},
        "time": {"startedLocal": local_time(original["started"]), "timezone": None,
                 "perTransactionTimestamps": "absent", "connectionIds": "absent"},
        "coverage": {"sourceArray": "transactions", "sourceEntries": len(ledger), "retainedEntries": len(ledger),
                     "droppedEntries": 0, "transactionEntries": len(operations), "eventEntries": len(ledger) - len(operations),
                     "outcomes": dict(sorted(collections.Counter(row["outcome"] for row in operations).items())),
                     "scalarPayloadsRetained": sum(key in row for row in operations for key in ("dataInLE", "dataOutLE")),
                     "payloadFieldsOmitted": sum(len(row.get("omittedPayloads", [])) for row in operations),
                     "emptyNamePayloadsRetained": sum(key in row for row in operations for key in ("emptyNameInHex", "emptyNameOutHex")),
                     "beforeSnapshots": len(before), "afterSnapshots": len(after),
                     "topLevelSnapshotPair": "recorded" if "banks_before" in original else "not_recorded",
                     "sourceCaptureCompleteness": "unknown"},
        "interpretation": {"sourceIndex": "zero-based original transactions array index; order preserved",
                           "transactionId": "source value; repeats across sessions and is not a unique identifier",
                           "rawPayloadEncoding": "hexadecimal bytes in source order, little-endian scalar interpretation",
                           "snapshotAndFindingNumbers": "unsigned integers unless explicitly labeled; not byte strings",
                           "responseOrigin": "not independently established by this host-generated log",
                           "events": "host-recorded camera_lost/camera_back, not proof of a power cycle; experiment_context keeps the operator's normalized AUTO UPDATE answer; bank_restore_verification keeps per-field statuses, not values",
                           "operatorObservations": "reviewed normalized observations with explicit source pointers; not independent menu or power telemetry",
                           "liveD1A5": "live setting sampled while a bank was selected, not a 24th bank field"},
        "transform": {"generator": "export.py", "generatorSha256": sha256(Path(exporter_path).read_bytes()),
                      "sharedGenerator": "../bankprobe_package.py", "sharedGeneratorSha256": sha256(Path(__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False, "losslessBackup": False,
                      "payloadAllowlist": [code(value) for value in sorted(SCALAR_CODES)], "maximumPayloadBytes": 4,
                      "omissions": ["command line and paths", "bank names and all D18D payloads except the two empty-name encodings (00 and 010000)",
                                    "DeviceInfo and D186/D187 payloads",
                                    "identity and device identifiers", "USB error text", "source verdict prose and ok flags",
                                    "unrestricted source strings and unknown fields"],
                      "generatedFacts": "No missing times, connection identifiers, conditions, or hardware observations are invented; finding interpretations are labeled."},
        "artifacts": {name: {"sha256": sha256(value), "bytes": len(value)} for name, value in outputs.items()},
    }
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs


def package_main(spec, build_findings, exporter_path, argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="private original outside the repository")
    parser.add_argument("--output-dir", type=Path, default=Path(exporter_path).resolve().parent)
    parser.add_argument("--check", action="store_true", help="compare deterministic artifacts without writing")
    args = parser.parse_args(argv)
    module_path = Path(__file__).resolve()
    repository = next((parent for parent in module_path.parents if (parent / ".git").exists()), module_path.parents[1])
    if args.original.resolve().is_relative_to(repository):
        parser.error("keep the original outside the repository")
    try:
        outputs = build_package(args.original.read_bytes(), spec, build_findings, exporter_path)
        if args.check:
            for name, expected in outputs.items():
                if (args.output_dir / name).read_bytes() != expected:
                    raise ValueError("generated artifact differs: " + name)
            print("Verified original hash and all %d deterministic artifacts." % len(outputs))
        else:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for name, value in outputs.items():
                (args.output_dir / name).write_bytes(value)
            print("Wrote %d sanitized artifacts; original unchanged." % len(outputs))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    return 0
