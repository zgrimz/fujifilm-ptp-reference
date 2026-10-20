#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted companion exports for individually reviewed, hash-pinned client camera reports.

The maintainers' iOS client exports a camera report whose `transactions` array is the PTP traffic
it handed to ImageCaptureCore on one connection: each command's operation and parameters, the
data it supplied or received (bytes only up to the client's dump limit), the response code and a
host-measured duration. Run-specific exporters select and normalize findings; this module keeps
transaction order and headers, the scalar payloads of the bank allowlist, and the two empty-name
encodings. It never copies bank names, DeviceInfo, identity or connection identifiers, error
text, push and develop records, or log lines, and it does not turn a client report into a
schema-v1 report.
"""

import argparse
import collections
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bankprobe_package  # noqa: E402
from bankprobe_package import (EMPTY_NAME_PAYLOADS, SCALAR_CODES, code, hex_integer,  # noqa: E402
                               integer, json_bytes, raw_scalar, sha256)

REPORT_VERSION = 6
# GetDevicePropDesc, GetDevicePropValue and SetDevicePropValue carry one parameter, a property code,
# which is kept. Every other operation's parameters (object handles, storage IDs) are only counted.
PROPERTY_OPERATIONS = frozenset({0x1014, 0x1015, 0x1016})
UTC_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
IDENTIFIER = re.compile(r"xt50-20261019-[0-9]{6}\Z")


def utc_time(value):
    if not isinstance(value, str) or not UTC_TIME.fullmatch(value):
        raise ValueError("expected a UTC timestamp")
    return value


def payload_bytes(original, direction):
    """The recorded bytes of one data phase, or None when the client recorded only a length."""
    payload = original.get(direction + "Data")
    length = original.get(direction + "DataLength")
    if payload is None:
        return None
    if not isinstance(payload, str) or not re.fullmatch(r"(?:[0-9A-Fa-f]{2})+", payload):
        raise ValueError("payload must be whole hexadecimal bytes")
    if length is None or len(payload) // 2 != integer(length):
        raise ValueError("payload and its recorded length disagree")
    return payload.lower()


def ledger_rows(rows):
    """Construct a fresh allowlisted row for every source transaction; no source dictionary is copied."""
    result = []
    for source_index, original in enumerate(rows):
        opcode = hex_integer(original["operation"])
        params = [hex_integer(value) for value in original["parameters"]]
        response = hex_integer(original["response"]) if original.get("response") is not None else None
        row = {"sourceIndex": source_index, "sequence": integer(original["sequence"]),
               "kind": "transaction", "opcode": code(opcode)}
        if opcode in PROPERTY_OPERATIONS:
            if len(params) != 1:
                raise ValueError("a property operation carries exactly one parameter")
            row["parameters"] = params
        else:
            row["parameterCount"] = len(params)
        row.update(response=code(response) if response is not None else None,
                   outcome=("recorded_ok" if response == 0x2001 else
                            "recorded_refusal" if response is not None else "outcome_unknown"),
                   transportErrorRecorded=original.get("error") is not None,
                   durationMs=integer(original["durationMs"]))
        prop = params[0] if opcode in (0x1015, 0x1016) else None
        for direction, target_key, empty_key, label in (("in", "dataInLE", "emptyNameInHex", "data_in"),
                                                        ("out", "dataOutLE", "emptyNameOutHex", "data_out")):
            if original.get(direction + "Data") is None and original.get(direction + "DataLength") is None:
                continue
            # Only a payload that might be retained is parsed; the client truncates long dumps, and
            # those (DeviceInfo, profiles) are omitted unread.
            payload = payload_bytes(original, direction) if prop in SCALAR_CODES | {0xD18D} else None
            if prop in SCALAR_CODES and payload is not None:
                row[target_key] = raw_scalar(payload)
            elif prop == 0xD18D and payload in EMPTY_NAME_PAYLOADS:
                row[empty_key] = payload
            else:
                # A name, an identity payload, a profile or an object: never copied, not even its length.
                row.setdefault("omittedPayloads", []).append(label)
        result.append(row)
    return result


def build_package(original_bytes, spec, build_findings, exporter_path):
    """Verify the reviewed source before any finding projection is invoked."""
    evidence_id = spec["evidenceId"]
    if not IDENTIFIER.fullmatch(evidence_id):
        raise ValueError("unexpected package identifier")
    if not re.fullmatch(r"[0-9a-f]{40}", spec["sourceRevision"]):
        raise ValueError("invalid source revision")
    if not re.fullmatch(r"hardware-runs/[a-z0-9-]+/[a-z-]+/[A-Za-z0-9.-]+\.json", spec["sourcePath"]):
        raise ValueError("invalid source path")
    if not re.fullmatch(r"[0-9a-f]{64}", spec["sourceSha256"]):
        raise ValueError("invalid source hash")
    if sha256(original_bytes) != spec["sourceSha256"]:
        raise ValueError("original SHA-256 does not match the reviewed run")
    original = json.loads(original_bytes)
    camera, host = original["camera"], original["host"]
    if (original["reportVersion"] != REPORT_VERSION or camera["identifiedModelID"] != "X-T50"
            or camera["identification"] != "exact" or camera["firmwareVersion"] != "1.32"):
        raise ValueError("unexpected source camera metadata")
    if original["traceScope"] != "connection" or original["transactionsDropped"] != 0:
        raise ValueError("the reviewed trace is one complete connection")
    ledger = ledger_rows(original["transactions"])
    if [row["sequence"] for row in ledger] != list(range(1, len(ledger) + 1)):
        raise ValueError("the trace's sequence numbers are not contiguous from 1")
    outputs = {
        "transactions.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
                                       for row in ledger),
        "findings.json": json_bytes({"format": "fuji-client-report-selected-observations-v1",
                                     "evidenceId": evidence_id, "findings": build_findings(original)}),
    }
    manifest = {
        "format": "fuji-client-report-sanitized-package-v1", "evidenceId": evidence_id,
        "evidenceKind": "measured_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": spec["sourcePath"],
                   "revision": spec["sourceRevision"], "sha256": spec["sourceSha256"], "bytes": len(original_bytes),
                   "reportFormatVersion": REPORT_VERSION},
        "camera": {"model": "X-T50", "firmware": "1.32", "provenance": "original_report",
                   "identification": "exact", "usbMode": None},
        "host": {"client": "the maintainers' iOS client, debug build", "operatingSystem": "iOS",
                 "systemVersion": host["systemVersion"], "transport": "ImageCaptureCore"},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None,
                       "imageFormat": spec.get("imageFormat", "unknown")},
        "time": {"traceStartedUtc": utc_time(original["traceStartedAt"]),
                 "reportUpdatedUtc": utc_time(original["updatedAt"]),
                 "perTransactionTimestamps": "absent", "connectionIds": "omitted"},
        "coverage": {"sourceArray": "transactions", "traceScope": "connection",
                     "sourceEntries": len(ledger), "retainedEntries": len(ledger), "droppedEntries": 0,
                     "sourceTransactionsDropped": 0,
                     "outcomes": dict(sorted(collections.Counter(row["outcome"] for row in ledger).items())),
                     "scalarPayloadsRetained": sum(key in row for row in ledger for key in ("dataInLE", "dataOutLE")),
                     "payloadFieldsOmitted": sum(len(row.get("omittedPayloads", [])) for row in ledger),
                     "emptyNamePayloadsRetained": sum(key in row for row in ledger
                                                      for key in ("emptyNameInHex", "emptyNameOutHex")),
                     "sourceCaptureCompleteness": "client_trace_only"},
        "interpretation": {"sourceIndex": "zero-based original transactions array index; order preserved",
                           "sequence": "the client's own count within the connection; not a PTP transaction ID",
                           "rawPayloadEncoding": "hexadecimal bytes in source order, little-endian scalar interpretation",
                           "dataPhase": "the bytes the client handed to ImageCaptureCore or received from it; the USB wire is not observed",
                           "responseOrigin": "the response code ImageCaptureCore returned to the client; not an independent bus capture",
                           "durationMs": "host-measured time from handing over the command to its completion",
                           "findingNumbers": "unsigned integers unless explicitly labeled; not byte strings"},
        "transform": {"generator": "export.py", "generatorSha256": sha256(Path(exporter_path).read_bytes()),
                      "sharedGenerator": "../client_report_package.py",
                      "sharedGeneratorSha256": sha256(Path(__file__).read_bytes()),
                      "helperModule": "../bankprobe_package.py",
                      "helperModuleSha256": sha256(Path(bankprobe_package.__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False, "losslessBackup": False,
                      "payloadAllowlist": [code(value) for value in sorted(SCALAR_CODES)], "maximumPayloadBytes": 4,
                      "omissions": ["bank names and all D18D payloads except the two empty-name encodings (00 and 010000)",
                                    "lengths of every omitted payload",
                                    "DeviceInfo, D186/D187, conversion-profile and object payloads",
                                    "parameters of operations other than property get, set and describe",
                                    "serial hash, USB identifiers, connection identifier and phone model",
                                    "error text, push, develop and camera-test records, slot reads and log lines"],
                      "generatedFacts": "No missing times, conditions, or hardware observations are invented; finding interpretations are labeled."},
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
