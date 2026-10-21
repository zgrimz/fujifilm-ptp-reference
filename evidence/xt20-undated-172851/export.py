#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted companion export of an X-T20 owner's app-log excerpt; the private original is read, never copied.

The original is the maintainers' iOS client's log of four connections to an X-T20, followed by the client's property
report for C1. Every line must match one of the reviewed line forms below or the export stops, so a serial number, a
serial hash, a name or any other line the review didn't see can't pass through as an unknown line. Each row is rebuilt
from the matched fields: times of day, model, firmware, PTP codes, counts and response codes. The USB vendor and
product identifiers, the client's property labels and its prose are not copied.
"""

import argparse
import collections
import datetime
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bankprobe_package  # noqa: E402
from bankprobe_package import code, hex_integer, json_bytes, sha256  # noqa: E402

SPEC = {"evidenceId": "xt20-undated-172851",
        "sourceSha256": "061306bc4670986ed312fa391e991f1cb819ca7b18ca6f997221128935486f62",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-x-t20/xt20.txt",
        "sourceLines": 150}

MODEL = "X-T20"
BLOCK = ["0x%04X" % value for value in range(0xD18C, 0xD1A6)]
STATUSES = {"ICAuthorizationStatusNotDetermined": "not_determined", "ICAuthorizationStatusAuthorized": "authorized",
            "ICAuthorizationStatusDenied": "denied", "ICAuthorizationStatusRestricted": "restricted"}
RESPONSES = {0x2002: "General Error", 0x200A: "DeviceProp Not Supported"}
# The client separates the time, its category tag and the message with two no-break spaces.
LOG_LINE = re.compile(r"([0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3})  \[camera\]  (.+)\Z")
STATUS = r"(ICAuthorizationStatus[A-Za-z]+)"
CODE_LIST = r"\[((?:0x[0-9A-F]{4} )*0x[0-9A-F]{4})\]"
INDENT = " " * 6
# A hexadecimal run longer than a 32-bit code: a serial hash, a payload or an identifier, never a reviewed field.
LONG_HEX = re.compile(r"[0-9A-Fa-f]{9,}")


def codes(text):
    return [code(hex_integer(value)) for value in text.split(" ")]


def response(value, name):
    if RESPONSES.get(hex_integer(value)) != name:
        raise ValueError("unexpected response name")
    return code(hex_integer(value))


# Each reviewed message form and the typed fields it keeps.
MESSAGES = [(re.compile(pattern + r"\Z"), build) for pattern, build in (
    (r"Connect: hardware connect requested", lambda m: {"event": "connect_requested"}),
    (r"Browser: (created|started) — control " + STATUS + ", contents " + STATUS,
     lambda m: {"event": "browser_" + m[1], "controlAuthorization": STATUSES[m[2]], "contentsAuthorization": STATUSES[m[3]]}),
    (r"Browser: control authorization is " + STATUS + r" — requesting",
     lambda m: {"event": "authorization_requested", "scope": "control", "status": STATUSES[m[1]]}),
    (r"Browser: control authorization request result — " + STATUS,
     lambda m: {"event": "authorization_result", "scope": "control", "status": STATUSES[m[1]]}),
    (r"Browser: (control|contents) authorization already granted",
     lambda m: {"event": "authorization_already_granted", "scope": m[1]}),
    (r"Browser: no device attached yet, waiting up to ([0-9]+)s",
     lambda m: {"event": "waiting_for_device", "timeoutSeconds": int(m[1])}),
    (r"Browser: didAdd X-T20 \(usb [0-9a-f]{4}:[0-9a-f]{4}\)", lambda m: {"event": "device_added", "model": MODEL}),
    (r"Browser: device already known — X-T20", lambda m: {"event": "device_already_known", "model": MODEL}),
    (r"Browser: didRemove X-T20", lambda m: {"event": "device_removed", "model": MODEL}),
    (r"Browser: did resume operations \(app foregrounded\)", lambda m: {"event": "app_foregrounded"}),
    (r"Browser: will suspend operations \(app backgrounding\)", lambda m: {"event": "app_backgrounding"}),
    (r"Browser: did suspend operations", lambda m: {"event": "operations_suspended"}),
    (r"Transport: session open \(X-T20\)", lambda m: {"event": "session_opened", "model": MODEL}),
    (r"Transport: closing \(X-T20\)", lambda m: {"event": "session_closing", "model": MODEL}),
    (r"Disconnect requested", lambda m: {"event": "disconnect_requested"}),
    (r'DeviceInfo: FUJIFILM X-T20 fw ([0-9]\.[0-9]{2}) · PTP ([0-9]+) · ext (0x[0-9A-F]{8}) '
     r'"fujifilm\.co\.jp: 1\.0; " · ([0-9]+) bytes',
     lambda m: {"event": "device_info", "manufacturer": "FUJIFILM", "model": MODEL, "firmware": m[1],
                "standardVersion": int(m[2]), "vendorExtensionID": m[3], "vendorExtensionDesc": "fujifilm.co.jp: 1.0; ",
                "datasetBytes": int(m[4])}),
    (r"DeviceInfo: operations " + CODE_LIST, lambda m: {"event": "device_info_operations", "operations": codes(m[1])}),
    (r"DeviceInfo: properties " + CODE_LIST, lambda m: {"event": "device_info_properties", "properties": codes(m[1])}),
    (r"DeviceInfo: slot protocol \(D18C/D18D\) NOT advertised · ([0-9]+) properties, ([0-9]+) operations",
     lambda m: {"event": "bank_protocol_not_advertised", "propertiesCount": int(m[1]), "operationsCount": int(m[2])}),
    (r"⚠️ Transport: PTP error (0x[0-9A-F]{4}) ([A-Za-z ]+)",
     lambda m: {"event": "ptp_error", "response": response(m[1], m[2])}),
)]

# The property report after the log. A label line names a property; the label is the client's and isn't copied.
REPORT = [(re.compile(pattern + r"\Z"), build) for pattern, build in (
    (r"", lambda m, prop: {"event": "blank"}),
    (r"_____", lambda m, prop: {"event": "separator"}),
    (r"Fuji Cookbook — camera property report", lambda m, prop: {"event": "property_report_start"}),
    (r"Camera: X-T20 · model X-T20 · firmware ([0-9]\.[0-9]{2})",
     lambda m, prop: {"event": "property_report_camera", "model": MODEL, "firmware": m[1]}),
    (r"Slot: C([1-7])", lambda m, prop: {"event": "property_report_heading", "bankLabel": int(m[1])}),
    (r"(D1[0-9A-F]{2})  [A-Za-z0-9 .()\-]{1,40}",
     lambda m, prop: {"event": "property_entry", "property": code(int(m[1], 16))}),
    (INDENT + r"holds:   The camera reported a protocol error \((0x[0-9A-F]{4})\) — ([A-Za-z ]+)\. "
     r"The camera was not changed\.",
     lambda m, prop: {"event": "value_read", "property": prop, "response": response(m[1], m[2])}),
    (INDENT + r"accepts: no descriptor \(camera answered (0x[0-9A-F]{4}) ([A-Za-z ]+)\)",
     lambda m, prop: {"event": "descriptor", "property": prop, "response": response(m[1], m[2])}),
    (INDENT + r"accepts: ((?:[0-9]+, )*[0-9]+)",
     lambda m, prop: {"event": "descriptor_enumeration", "property": prop,
                      "enumeration": [int(value) for value in m[1].split(", ")]}),
    (INDENT + r"(UINT16) · (read/write|read-only) · default ([0-9]+) · descriptor current ([0-9]+)",
     lambda m, prop: {"event": "descriptor_detail", "property": prop, "dataType": m[1],
                      "writable": m[2] == "read/write", "factoryDefault": int(m[3]), "current": int(m[4])}),
)]


def log_rows(text):
    """One allowlisted row per source line, in order; a line no reviewed form matches stops the export."""
    rows, report, prop = [], False, None
    for number, line in enumerate(text.split("\n"), 1):
        match = None if report else LOG_LINE.fullmatch(line)
        if match:
            for pattern, build in MESSAGES:
                found = pattern.fullmatch(match[2])
                if found:
                    rows.append({"sourceLine": number, "kind": "log", "localTime": match[1], **build(found)})
                    break
            else:
                raise ValueError("unreviewed log line %d" % number)
            continue
        report = True
        for pattern, build in REPORT:
            found = pattern.fullmatch(line)
            if found:
                row = build(found, prop)
                if row["event"] == "property_entry":
                    prop = row["property"]
                elif "property" in row and prop is None:
                    raise ValueError("property detail before any property entry")
                rows.append({"sourceLine": number, "kind": "property_report", **row})
                break
        else:
            raise ValueError("unreviewed report line %d" % number)
    return rows


def milliseconds(earlier, later):
    parse = lambda value: datetime.datetime.strptime(value, "%H:%M:%S.%f")  # noqa: E731
    return round((parse(later) - parse(earlier)).total_seconds() * 1000)


def findings(rows):
    log = [row for row in rows if row["kind"] == "log"]
    opens = [index for index, row in enumerate(log) if row["event"] == "session_opened"]
    connections = []
    for number, start in enumerate(opens):
        stop = opens[number + 1] if number + 1 < len(opens) else len(log)
        segment = log[start:stop]
        events = [row["event"] for row in segment]
        info = segment[events.index("device_info")]
        operations = segment[events.index("device_info_operations")]["operations"]
        properties = segment[events.index("device_info_properties")]["properties"]
        summary = segment[events.index("bank_protocol_not_advertised")]
        error = segment[events.index("ptp_error")]
        if (summary["propertiesCount"], summary["operationsCount"]) != (len(properties), len(operations)) or \
                events.index("ptp_error") != events.index("bank_protocol_not_advertised") + 1:
            raise ValueError("connection %d differs from the reviewed shape" % (number + 1))
        closing = [row for row in segment if row["event"] == "session_closing"]
        connections.append({"connection": number + 1, "sessionOpenedLine": segment[0]["sourceLine"],
                            "deviceInfoLine": info["sourceLine"],
                            "sessionOpenToDeviceInfoLogMs": milliseconds(segment[0]["localTime"], info["localTime"]),
                            "operationsCount": len(operations), "propertiesCount": len(properties),
                            "errorAfterDeviceInfo": {"line": error["sourceLine"], "response": error["response"],
                                                     "logMsAfterDeviceInfo": milliseconds(info["localTime"], error["localTime"])},
                            "sessionClosingLine": closing[0]["sourceLine"] if closing else None})
        connections[-1]["_lists"] = ({key: value for key, value in info.items() if key not in ("sourceLine", "localTime", "kind")},
                                     operations, properties)
    first = connections[0]["_lists"]
    if len(connections) != 4 or any(connection.pop("_lists") != first for connection in connections):
        raise ValueError("expected four connections with identical DeviceInfo")
    device_info, operations, properties = first
    if (device_info["firmware"], device_info["datasetBytes"], len(operations), len(properties)) != ("2.01", 595, 27, 168) or \
            any(0xD162 <= int(prop, 16) <= 0xD1FF for prop in properties):
        raise ValueError("DeviceInfo differs from the reviewed run")
    report = [row for row in rows if row["kind"] == "property_report"]
    entries = collections.OrderedDict()
    for row in report:
        if row["event"] == "property_entry":
            entries[row["property"]] = {"property": row["property"]}
        elif row["event"] == "value_read":
            entries[row["property"]]["valueResponse"] = row["response"]
        elif row["event"] == "descriptor":
            entries[row["property"]]["descriptorResponse"] = row["response"]
        elif row["event"] == "descriptor_enumeration":
            entries[row["property"]]["descriptor"] = {"enumeration": row["enumeration"]}
        elif row["event"] == "descriptor_detail":
            entries[row["property"]]["descriptor"].update(
                {key: row[key] for key in ("dataType", "writable", "factoryDefault", "current")})
    entries = list(entries.values())
    expected = [{"property": prop, "valueResponse": "0x200A", "descriptorResponse": "0x200A"} for prop in BLOCK] + \
        [{"property": "0xD185", "valueResponse": "0x2002", "descriptorResponse": "0x200A"},
         {"property": "0xD183", "valueResponse": "0x200A",
          "descriptor": {"enumeration": [0, 1], "dataType": "UINT16", "writable": True, "factoryDefault": 65535,
                         "current": 65535}}]
    heading = [row for row in report if row["event"] == "property_report_heading"]
    camera = [row for row in report if row["event"] == "property_report_camera"]
    if entries != expected or [row["bankLabel"] for row in heading] != [1] or [row["firmware"] for row in camera] != ["2.01"]:
        raise ValueError("property report differs from the reviewed run")
    return {"deviceInfo": {**device_info, "operations": operations, "properties": properties,
                           "identicalAcrossConnections": 4, "propertiesFromD162ToD1FF": 0,
                           "bankBlockAdvertised": any(prop in properties for prop in BLOCK),
                           "d183Advertised": "0xD183" in properties, "d185Advertised": "0xD185" in properties},
            "connections": connections,
            "propertyReport": {"headingBankLabel": 1, "entries": entries,
                               "bankBlock": {"properties": len(BLOCK), "valueResponse": "0x200A",
                                             "descriptorResponse": "0x200A"},
                               "d185": entries[-2], "d183": entries[-1]},
            "notEstablished": ["the log's date and time zone", "the client build and the host's system version",
                               "USB mode and any 0xD16E reading", "whether a selector write succeeded; the report's C1 "
                               "heading is the client's label", "which connection the property report came from",
                               "which property read produced the error logged after each DeviceInfo",
                               "any RAF upload or conversion",
                               "AUTO UPDATE CUSTOM SETTING, ISO, lens and image format"]}


def build_package(original_bytes, spec, exporter_path):
    """Verify the reviewed source before any line is parsed."""
    if sha256(original_bytes) != spec["sourceSha256"]:
        raise ValueError("original SHA-256 does not match the reviewed log")
    text = original_bytes.decode("utf-8")
    rows = log_rows(text)
    if len(rows) != spec["sourceLines"]:
        raise ValueError("line count differs from the reviewed log")
    outputs = {
        "log.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
                              for row in rows),
        "findings.json": json_bytes({"format": "fuji-owner-app-log-selected-observations-v1",
                                     "evidenceId": spec["evidenceId"], "findings": findings(rows)}),
    }
    if any(LONG_HEX.search(value.decode("utf-8")) for value in outputs.values()):
        raise ValueError("an output holds a hexadecimal run longer than a PTP code")
    log = [row for row in rows if row["kind"] == "log"]
    manifest = {
        "format": "fuji-owner-app-log-sanitized-package-v1", "evidenceId": spec["evidenceId"],
        "evidenceKind": "owner_report_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": spec["sourcePath"], "revision": spec["sourceRevision"],
                   "sha256": spec["sourceSha256"], "bytes": len(original_bytes), "lines": len(rows),
                   "encoding": "UTF-8, no final newline"},
        "camera": {"model": MODEL, "firmware": "2.01", "provenance": "owner_report", "usbMode": None},
        "host": {"client": "the maintainers' iOS client; build not recorded", "operatingSystem": "iOS or iPadOS",
                 "systemVersion": None, "transport": "ImageCaptureCore"},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None, "imageFormat": "unknown"},
        "time": {"date": None, "receivedLocalDate": "2026-09-14", "timezone": None,
                 "firstLocalTime": log[0]["localTime"], "lastLocalTime": log[-1]["localTime"],
                 "identifierClock": "the first log line's local time of day; the log carries no date"},
        "coverage": {"sourceLines": len(rows), "retainedLines": len(rows), "droppedLines": 0, "logLines": len(log),
                     "propertyReportLines": len(rows) - len(log),
                     "events": dict(sorted(collections.Counter(row["event"] for row in rows).items())),
                     "connections": 4, "propertyReportEntries": 28},
        "interpretation": {"sourceLine": "one-based line number in the original; order preserved",
                           "localTime": "the client's log time of day, with no date or offset",
                           "logIntervals": "differences between log-line times; not PTP transaction durations",
                           "propertyReport": "the client's report after the log; which connection it came from is not recorded",
                           "bankLabel": "the report's heading, not evidence of a successful selector write"},
        "transform": {"generator": "export.py", "generatorSha256": sha256(Path(exporter_path).read_bytes()),
                      "helperModule": "../bankprobe_package.py",
                      "helperModuleSha256": sha256(Path(bankprobe_package.__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False, "losslessBackup": False,
                      "reviewedLineForms": len(MESSAGES) + len(REPORT), "unreviewedLines": "refused",
                      "omissions": ["USB vendor and product identifiers", "the client's property labels and prose",
                                    "the log's category tag"],
                      "serialCheck": "the original holds no serial number or serial hash; no reviewed line form admits "
                                     "one, and the outputs are refused if any holds a hexadecimal run longer than a PTP code",
                      "generatedFacts": "No missing dates, conditions, or hardware observations are invented; finding interpretations are labeled."},
        "artifacts": {name: {"sha256": sha256(value), "bytes": len(value)} for name, value in outputs.items()},
    }
    outputs["manifest.json"] = json_bytes(manifest)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="private original outside the repository")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true", help="compare deterministic artifacts without writing")
    args = parser.parse_args(argv)
    module_path = Path(__file__).resolve()
    repository = next((parent for parent in module_path.parents if (parent / ".git").exists()), module_path.parents[2])
    if args.original.resolve().is_relative_to(repository):
        parser.error("keep the original outside the repository")
    try:
        outputs = build_package(args.original.read_bytes(), SPEC, __file__)
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
    except (OSError, ValueError, KeyError, UnicodeDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
