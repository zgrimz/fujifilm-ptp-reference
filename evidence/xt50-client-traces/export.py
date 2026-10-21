#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted trace-only exports of the maintainers' own X-T50 client camera reports; originals are read, never copied.

Each package keeps one report's PTP trace through the client-report ledger (client_report_package.ledger_rows,
unchanged) and mechanical observations over it (owner_report_package.observations, shared with the GFX100S packages).
The client's own records, such as bank reads, pushes, guided tests, develops, and notes, aren't projected at all.
Before anything is written, every output is searched for each bank, recipe, and identity string the original holds,
as plain text, as JSON escapes, and as the UTF-16 hexadecimal a PTP string carries; one hit stops the export. The one
identity field a manifest keeps is the client's keyed camera identifier (client_report_package.keyed_identifier), which
reports from 2026-10-15 carry; an unkeyed serial hash stays in the searched set.

Pass an original; the exporter finds its package by the original's SHA-256 and writes into that package's folder.
"""

import argparse
import collections
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bankprobe_package  # noqa: E402
import client_report_package  # noqa: E402
import owner_report_package  # noqa: E402
from bankprobe_package import EMPTY_NAME_PAYLOADS, SCALAR_CODES, code, json_bytes, sha256  # noqa: E402

REVISION = "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9"
DIRECTORY = "hardware-runs/app-reports-x-t50/camera-reports"
# Package identifier: (original's SHA-256, file name, traced transactions).
SPECS = {
    "xt50-20260906-180652": ("aa203923cf7dcf289a9240ba85ea1b21815863ffb702152636dd1295b8cc1f8c", "fuji-cookbook-camera-report-X-T50-20260906-1806.json", 183),
    "xt50-20260906-182230": ("aa0b26b32ad8eab30df66fe95f933c7a1efcfc3aab8f839c1f4ffc23df5d6452", "fuji-cookbook-camera-report-X-T50-20260906-1822.json", 183),
    "xt50-20260906-191557": ("e4907fa5365ffc4468a9ea93a63ed30c9833e2f7b9a8ef32f8bcb60b989d1cc7", "fuji-cookbook-camera-report-X-T50-20260906-1915.json", 190),
    "xt50-20260906-195112": ("49328c64d5e6991c5e733fbd49916baddd1fceba352833400678a03499f42815", "fuji-cookbook-camera-report-X-T50-20260906-1951.json", 190),
    "xt50-20260906-200420": ("f0c2f7cb3e48cf8f837a743d7a49b12c47786b1a10cd9afd6e173a5e655219c7", "fuji-cookbook-camera-report-X-T50-20260906-2004.json", 190),
    "xt50-20260907-163145": ("a81693a3aa1f578bb768ab91695689a59be70aac424e92110b46ecdcd41b06e3", "fuji-cookbook-camera-report-X-T50-20260907-1631.json", 694),
    "xt50-20260914-200137": ("28fa59e0ca983107eec3ee193d9e301b195b3119510db476ec2fc0184072a10f", "fuji-cookbook-camera-report-X-T50-20260914-2001.json", 247),
    "xt50-20260914-203438": ("8ddbb6eac79cac5ec18174b2511190f62ab14e1650282e9d2fce614cadfab3f3", "fuji-cookbook-camera-report-X-T50-20260914-2034.json", 257),
    "xt50-20260914-203812": ("8cc86d1906df4bc1c14d4de3f94ff21275572e344b0c91caf855b20e67f4e384", "fuji-cookbook-camera-report-X-T50-20260914-2038.json", 265),
    "xt50-20260914-205600": ("33a42f24dd3cae8520e8a8644ee3d45c97a1d831dd5bb7a08c2c10b9ba44635f", "fuji-cookbook-camera-report-X-T50-20260914-2056.json", 257),
    "xt50-20260914-205836": ("8bcb542406ba661fa16b9e1f99420296fef365f2cec01aae88d687b157283a89", "fuji-cookbook-camera-report-X-T50-20260914-2058.json", 265),
    "xt50-20260914-210459": ("397e230a80bb83a6a289a4167d43d9930602fad806828f6d110d97fe10db9f62", "fuji-cookbook-camera-report-X-T50-20260914-2104.json", 281),
    "xt50-20260914-210650": ("495fc734510016aeb92b2ab4b036d3e3c71bd763cde2b5491e9761fb3fa34427", "fuji-cookbook-camera-report-X-T50-20260914-2106.json", 263),
    "xt50-20260915-225954": ("fd13b0e6c0afa0ff39910e02e6d809d9b976a2d149ec422daa1214d96ff48943", "fuji-cookbook-camera-report-X-T50-20260915-2259.json", 700),
    "xt50-20260920-165222": ("afbf287ac1ef0029ea9883cee9af09cd0f42a3aff774f1f28666067e3b0250df", "fuji-cookbook-camera-report-X-T50-20260920-1652.json", 1200),
    "xt50-20260920-170753": ("c969287c6c01c61b45dbfc5a2f17e84fca62f07a9d42efd163e549d6568da6cd", "fuji-cookbook-camera-report-X-T50-20260920-1707.json", 340),
    "xt50-20260920-171710": ("32855ba084c333dc8c5e0a6818a2e48c8bdec1b5a51e16105e262d9d1f8a8fca", "fuji-cookbook-camera-report-X-T50-20260920-1717.json", 266),
    "xt50-20260920-173842": ("9088988c6578325b1aac7aa6b2f32c738a96900ac4eb6d127399e27411e7f44b", "fuji-cookbook-camera-report-X-T50-20260920-1738.json", 267),
    "xt50-20261003-132005": ("a8bb9549189caae538dd689c57f9d888725a7261bef28024ac6e6dd651d7c944", "fuji-cookbook-camera-report-X-T50-20261003-1320.json", 255),
    "xt50-20261003-133415": ("35965c183a2ab8d26415f054a10725e4dcc607f2e7aebd441c70010f092c0478", "fuji-cookbook-camera-report-X-T50-20261003-1334.json", 279),
    "xt50-20261003-143543": ("a8cd18878fe38ec50096d1937b8c8fb45d23ee59123e470ffff1b3e15b8705e6", "fuji-cookbook-camera-report-X-T50-20261003-1435.json", 279),
    "xt50-20261003-214040": ("b36cd30cddba24dd1ab1bd7124294f323bf1fabfdad274a9a2375913d4a4c547", "fuji-cookbook-camera-report-X-T50-20261003-2140.json", 255),
    "xt50-20261003-222000": ("3bfe4b6082b6702b3eed7d0f641f227ddef294c2cd18b2493045b40b3625db34", "fuji-cookbook-camera-report-X-T50-20261003-2220.json", 353),
    "xt50-20261015-172015": ("aeb780d17c7cf0ef0aae41237dc140101e7bf8067dc5ac0ab91d73e5d9d897ce", "fuji-cookbook-camera-report-X-T50-20261015-1720.json", 200),
    "xt50-20261017-175208": ("0cbf0802a0611da4db1cc14ef27cbda26949c72232a83c8bd4eb7ab3c7c68225", "fuji-cookbook-camera-report-X-T50-20261017-1752.json", 279),
    "xt50-20261018-173731": ("3b531f0e07902445398390484140a0187ecefb01b63d7fcf2e85c13212102107", "fuji-cookbook-camera-report-X-T50-20261018-1737.json", 301),
    "xt50-20261018-174411": ("f276113f1e38b7b2e9c0ff428137577f201033e704234ee8781a07ba1518589a", "fuji-cookbook-camera-report-X-T50-20261018-1744.json", 258),
    "xt50-20261019-101935": ("7bf7445df2def9844914cfb0d38ab62c076a121592146e85d2b71a67dd9ac909", "fuji-cookbook-camera-report-X-T50-20261019-1019.json", 258),
    "xt50-20261019-102134": ("4cda57b1a8c98b13f4480984d0d7e433963ca67b055b2f1bc3a02e1a99a5f8bd", "fuji-cookbook-camera-report-X-T50-20261019-1021.json", 200),
}
REPORT_VERSIONS = frozenset({2, 4, 5, 6})
# Keys under which the client keeps a bank or recipe name, or an identifier for the camera, the phone, a connection,
# a session, or a record. Their values never reach an output; the check below proves it for each export.
PRIVATE_KEYS = frozenset({"serialHash", "deviceIdentifier", "connectionID", "sessionID", "resultID", "runID", "evidenceID",
                          "savedBatchID", "recoveryBaselineID", "nameApplied", "nameBefore", "recipeName", "currentName",
                          "expectedName", "originalName", "nameReadBack"})
# A "name" key is a bank or recipe name, except where it labels a property, an operation, or a field.
LABEL_PARENTS = frozenset({"properties", "fields", "entries", "operationsSupported", "devicePropertiesSupported"})
UUID = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\Z", re.I)


def private_strings(original):
    """Every private string in the original with its encoded forms, found by key, by shape, and by payload."""
    names, found = set(), set()

    def walk(value, key=None, parent=None):
        if isinstance(value, dict):
            for child_key, child in value.items():
                if UUID.fullmatch(child_key):
                    found.add(child_key)
                walk(child, child_key, key)
        elif isinstance(value, list):
            for child in value:
                walk(child, key, parent if key is None else key)
        elif isinstance(value, str):
            if key in PRIVATE_KEYS or (key == "id" and UUID.fullmatch(value)) or UUID.fullmatch(value):
                (names if "ame" in key else found).add(value)
            elif key == "name" and parent not in LABEL_PARENTS:
                names.add(value)
            elif key == "notes":
                found.add(value)

    walk({key: value for key, value in original.items() if key != "transactions"})
    for entry in original["transactions"]:
        hidden = entry["operation"] in ("0x900C", "0x100C") or entry["parameters"] == ["0xD18D"]
        for direction in ("in", "out"):
            payload = entry.get(direction + "Data")
            if hidden and isinstance(payload, str):
                payload = re.match(r"[0-9A-Fa-f]*", payload)[0].lower()
                if payload not in EMPTY_NAME_PAYLOADS:
                    found.add(payload)
    for sweep in [original.get("propertySweep")] + [test.get("propertySweep") for test in original.get("guidedTests", [])]:
        for entry in (sweep or {}).get("entries", []):
            if entry.get("code") == "0xD18D" and isinstance(entry.get("value"), str) and \
                    entry["value"].lower() not in EMPTY_NAME_PAYLOADS:
                found.add(entry["value"].lower())
    for name in names - {"", "X-T50"}:
        utf16 = name.encode("utf-16-le").hex()
        found.update((name, json.dumps(name)[1:-1], utf16, utf16 + "0000"))
    return {value.lower() for value in found if len(value) >= 4}


def build_package(original_bytes, evidence_id, exporter_path):
    """Verify the reviewed source before any projection runs."""
    source_sha, file_name, count = SPECS[evidence_id]
    if sha256(original_bytes) != source_sha:
        raise ValueError("original SHA-256 does not match the reviewed report")
    original = json.loads(original_bytes)
    camera = original["camera"]
    if original["reportVersion"] not in REPORT_VERSIONS or (camera.get("identifiedModelID"), camera["firmwareVersion"]) != \
            ("X-T50", "1.32"):
        raise ValueError("unexpected source camera metadata")
    if original["transactionsDropped"] != 0 or len(original["transactions"]) != count:
        raise ValueError("the reviewed trace is one complete client trace")
    ledger = client_report_package.ledger_rows(original["transactions"])
    if [row["sequence"] for row in ledger] != list(range(1, len(ledger) + 1)):
        raise ValueError("the trace's sequence numbers are not contiguous from 1")
    reads = [entry["durationMs"] for entry in original["transactions"]
             if entry["operation"] == "0x1015" and entry["parameters"] != ["0xD185"]]
    outputs = {
        "transactions.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
                                       for row in ledger),
        "findings.json": json_bytes({"format": "fuji-client-trace-observations-v1", "evidenceId": evidence_id,
                                     "observations": owner_report_package.observations(original),
                                     "propertyReads": {"basis": "every GetDevicePropValue except the 0xD185 profile",
                                                       "count": len(reads), "maximumMs": max(reads) if reads else None}}),
    }
    secrets = private_strings(original)
    owner_report_package.check_disclosure(outputs, secrets)
    # Only a keyed identifier leaves the private set, and only into the manifest; an unkeyed hash stays private.
    identifier = client_report_package.keyed_identifier(camera)
    if identifier:
        secrets.discard(identifier["value"])
    app, host = original["app"], original["host"]
    manifest = {
        "format": "fuji-client-trace-sanitized-package-v1", "evidenceId": evidence_id,
        "evidenceKind": "measured_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": DIRECTORY + "/" + file_name, "revision": REVISION,
                   "sha256": source_sha, "bytes": len(original_bytes), "reportFormatVersion": original["reportVersion"]},
        "camera": {"model": "X-T50", "firmware": "1.32", "provenance": "original_report",
                   "identification": owner_report_package.enum(camera["identification"], {"exact"}), "usbMode": None,
                   "identifier": identifier},
        "host": {"client": "the maintainers' iOS client, %s build %d" % (
                     owner_report_package.enum(app["channel"], {"debug", "testflight"}), int(app["build"])),
                 "operatingSystem": "iOS or iPadOS",
                 "systemVersion": owner_report_package.enum(host["systemVersion"], {"26.6.1", "26.6.2", "27.0.1"}),
                 "deviceModel": "omitted", "transport": "ImageCaptureCore"},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None, "imageFormat": "unknown"},
        "time": {"reportGeneratedUtc": owner_report_package.utc(original["generatedAt"]),
                 "reportUpdatedUtc": owner_report_package.utc(original["updatedAt"]),
                 "traceStartedUtc": owner_report_package.utc(original["traceStartedAt"]) if "traceStartedAt" in original else None,
                 "identifierClock": "the report's generatedAt in the maintainers' local time, UTC-4, which the archive file names use",
                 "perTransactionTimestamps": "absent", "connectionIds": "omitted"},
        "coverage": {"sourceArray": "transactions", "traceScope": original.get("traceScope", "not recorded in this report version"),
                     "sourceEntries": len(ledger), "retainedEntries": len(ledger), "droppedEntries": 0,
                     "sourceTransactionsDropped": 0,
                     "outcomes": dict(sorted(collections.Counter(row["outcome"] for row in ledger).items())),
                     "scalarPayloadsRetained": sum(key in row for row in ledger for key in ("dataInLE", "dataOutLE")),
                     "payloadFieldsOmitted": sum(len(row.get("omittedPayloads", [])) for row in ledger),
                     "emptyNamePayloadsRetained": sum(key in row for row in ledger
                                                      for key in ("emptyNameInHex", "emptyNameOutHex")),
                     "clientRecords": "not projected", "privateStringsChecked": len(secrets),
                     "sourceCaptureCompleteness": "client_trace_only"},
        "interpretation": {"sourceIndex": "zero-based original transactions array index; order preserved",
                           "sequence": "the client's own count within its trace; not a PTP transaction ID",
                           "rawPayloadEncoding": "hexadecimal bytes in source order, little-endian scalar interpretation",
                           "dataPhase": "the bytes the client handed to ImageCaptureCore or received from it; the USB wire is not observed",
                           "responseOrigin": "the response code ImageCaptureCore returned to the client; not an independent bus capture",
                           "durationMs": "host-measured time from handing over the command to its completion",
                           "findingNumbers": "unsigned integers unless explicitly labeled; not byte strings"},
        "transform": {"generator": "../export.py", "generatorSha256": sha256(Path(exporter_path).read_bytes()),
                      "ledgerModule": "../../client_report_package.py",
                      "ledgerModuleSha256": sha256(Path(client_report_package.__file__).read_bytes()),
                      "observationModule": "../../owner_report_package.py",
                      "observationModuleSha256": sha256(Path(owner_report_package.__file__).read_bytes()),
                      "helperModule": "../../bankprobe_package.py",
                      "helperModuleSha256": sha256(Path(bankprobe_package.__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False, "losslessBackup": False,
                      "payloadAllowlist": [code(value) for value in sorted(SCALAR_CODES)], "maximumPayloadBytes": 4,
                      "omissions": ["every client record: bank reads, pushes, guided tests, develops, property sweeps and notes",
                                    "unkeyed serial hashes, host device model, connection, session, run and result identifiers, and USB "
                                    "identifiers; only the keyed hmac-sha256 camera identifier is kept",
                                    "bank and recipe names, and all D18D payloads except the two empty-name encodings (00 and 010000)",
                                    "lengths of every omitted payload",
                                    "DeviceInfo, descriptor, conversion-profile and object payloads",
                                    "parameters of operations other than property get, set and describe"],
                      "disclosureCheck": "every output searched for each private string of the original, plain, JSON-escaped and UTF-16 hex",
                      "generatedFacts": "No missing times, conditions, or hardware observations are invented."},
        "artifacts": {name: {"sha256": sha256(value), "bytes": len(value)} for name, value in outputs.items()},
    }
    outputs["manifest.json"] = json_bytes(manifest)
    owner_report_package.check_disclosure(outputs, secrets)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="private original outside the repository")
    parser.add_argument("--output-dir", type=Path, help="defaults to this folder's package for the original")
    parser.add_argument("--check", action="store_true", help="compare deterministic artifacts without writing")
    args = parser.parse_args(argv)
    module_path = Path(__file__).resolve()
    repository = next((parent for parent in module_path.parents if (parent / ".git").exists()), module_path.parents[2])
    if args.original.resolve().is_relative_to(repository):
        parser.error("keep the original outside the repository")
    try:
        original_bytes = args.original.read_bytes()
        matches = [evidence_id for evidence_id, spec in SPECS.items() if spec[0] == sha256(original_bytes)]
        if not matches:
            raise ValueError("original SHA-256 matches no reviewed report")
        evidence_id, = matches
        outputs = build_package(original_bytes, evidence_id, __file__)
        output_dir = args.output_dir or module_path.parent / evidence_id
        if args.check:
            for name, expected in outputs.items():
                if (output_dir / name).read_bytes() != expected:
                    raise ValueError("generated artifact differs: " + name)
            print("%s: verified original hash and all %d deterministic artifacts." % (evidence_id, len(outputs)))
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            for name, value in outputs.items():
                (output_dir / name).write_bytes(value)
            print("%s: wrote %d sanitized artifacts; original unchanged." % (evidence_id, len(outputs)))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
