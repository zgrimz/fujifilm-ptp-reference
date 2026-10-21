#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted companion exports for hash-pinned camera reports a GFX100S owner exported from the maintainers' iOS client.

The owner's reports are versions 4 and 5 of the client report the X-T50 client-report packages use. The
transaction ledger comes from client_report_package.ledger_rows, unchanged. This module adds an allowlisted
projection of the client's own records (bank reads, the property sweep, pushes, guided-test steps and menu
comparisons, profile harvests and notes) and mechanical observations over the trace. Every value is rebuilt
from a parsed, typed field; a string survives only from a reviewed enumeration, a strict pattern, or the
client's display text for a camera setting. Unknown keys stop the export rather than pass through.

Before anything is written, every output is searched for every bank name, serial hash, host device identifier,
session identifier, name payload and object-info payload the original holds, as plain text, as JSON escapes,
and as the UTF-16 hexadecimal a PTP string carries. One hit stops the export.
"""

import argparse
import collections
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bankprobe_package  # noqa: E402
import client_report_package  # noqa: E402
from bankprobe_package import (BANK_CODES, EMPTY_NAME_PAYLOADS, SCALAR_CODES, code, hex_integer,  # noqa: E402
                               integer, json_bytes, raw_scalar, sha256)

MODEL = "GFX100S"
REPORT_VERSIONS = frozenset({4, 5})
IDENTIFIER = re.compile(r"gfx100s-202609(?:15|17|29)-[0-9]{6}\Z")
SOURCE_PATH = re.compile(r"hardware-runs/app-reports-gfx100s/2026-09-(?:15|17|29)/[A-Za-z0-9 .-]+\.json\Z")
UTC_TIME = client_report_package.UTC_TIME
FIRMWARE = re.compile(r"[0-9]\.[0-9]{2}\Z")
# The client's rendering of a camera setting, as it showed it beside the camera's own menu: letters, digits and
# the punctuation its value formatter uses. A bank name could match this too, which is why the disclosure check
# runs over every output afterwards.
DISPLAY_TEXT = re.compile(r"[A-Za-z0-9 +\-−.,/·()?]{1,48}\Z")
RESPONSES = {0x2001: "OK", 0x2002: "General Error", 0x200A: "DeviceProp Not Supported",
             0x201C: "Invalid DeviceProp Value"}
STEPS = frozenset({"intro", "connect", "confirmIdentity", "readSlots", "compareSlots", "propertyReport", "grainProbe",
                   "develop", "review", "send", "writeIntro", "backup", "chooseRecipe", "chooseSlot", "push",
                   "powerCycle", "recheckSlot", "photoCheck", "moreTrials", "restoreOffer"})
COMPARISON_FIELDS = frozenset({"Film Simulation", "Monochromatic Color", "Grain Effect", "Color Chrome Effect",
                               "Color Chrome FX Blue", "White Balance", "Dynamic Range", "D-Range Priority",
                               "Highlight Tone", "Shadow Tone", "Color", "Sharpness", "High ISO NR", "Clarity"})
BADGES = frozenset({"Read & Write · unverified", "Read & Write · owner-verified"})
DETAILS = {"RAW conversion isn't enabled for this body.": "conversion_not_enabled_for_body",
           "This body isn't one Fuji Cookbook writes to, so nothing was written to probe with.": "body_not_written"}
VALUE_ERROR = re.compile(r"The camera reported a protocol error \((0x[0-9A-F]{4})\) — ([A-Za-z ]+)\. "
                         r"The camera was not changed\.\Z")
DESCRIPTOR_ERROR = re.compile(r"no descriptor \(camera answered (0x[0-9A-F]{4}) ([A-Za-z ]+)\)\Z")
SELECT_ERROR = re.compile(r"(0x[0-9A-F]{4}) ([A-Za-z ]+)\Z")
PROFILE_ERROR = re.compile(r"(0x[0-9A-F]{4}) ([A-Za-z ]+)\Z")
GRAIN_STEP = re.compile(r"([0-9]+)→(?:rejected \((0x[0-9A-F]{4}) ([A-Za-z ]+)\)|(ACCEPTED)|OK, reads back ([0-9]+))\Z")
HARVEST_DETAIL = re.compile(r"([0-9]+)-byte profile, layout resolved at base 0x([0-9A-F]+)\Z")
HARVEST_HEAD = re.compile(r"([0-9]+) bytes / ([0-9]+) params / IOPCode ([0-9A-F]{8}) → canonical base 0x([0-9A-F]+), "
                          r"tail base 0x([0-9A-F]+)\Z")
HARVEST_CANDIDATE = re.compile(r"  base 0x([0-9A-F]+): DR=([0-9]+) sim=(.+) score=([0-9]+) (OK|rejected)\Z")
PROFILE_HEAD_LINE = re.compile(r"([0-9a-f]{4})  ([0-9A-F]{32})\Z")
NOTES = (
    (re.compile(r"C([1-7]): slot select refused \((0x[0-9A-F]{4}) ([A-Za-z ]+)\) — this body has ([1-7]) slots\Z"),
     lambda m: {"kind": "bank_select_refused", "bank": int(m[1]), "response": response(m[2], m[3]),
                "bankCountReported": int(m[4])}),
    (re.compile(r"write probe Grain Effect C([1-7]): (.+)\Z"),
     lambda m: {"kind": "grain_write_probe", "bank": int(m[1]), "steps": grain_steps(m[2])}),
    (re.compile(r"profile harvest: ([0-9]+)-byte profile, layout resolved at base 0x([0-9A-F]+)\Z"),
     lambda m: {"kind": "profile_harvest", "profileBytes": int(m[1]), "tableOffset": int(m[2], 16)}),
    (re.compile(r"C([1-7]): ((?:0x[0-9A-F]{4} ?)+) withheld — this body answers (0x[0-9A-F]{4}) to them, "
                r"and they carry the slot's own value\Z"),
     lambda m: {"kind": "properties_withheld", "bank": int(m[1]),
                "properties": [code(hex_integer(value)) for value in m[2].split()],
                "responseReported": response(m[3], RESPONSES.get(hex_integer(m[3]), ""))}),
)


def keys(original, allowed, dropped=()):
    """Fail closed: a key that is neither projected nor reviewed as dropped stops the export."""
    if not isinstance(original, dict):
        raise ValueError("expected an object")
    unknown = set(original) - set(allowed) - set(dropped)
    if unknown:
        raise ValueError("unreviewed source fields: " + ", ".join(sorted(unknown)))
    return original


def boolean(value):
    if type(value) is not bool:
        raise ValueError("expected a boolean")
    return value


def utc(value):
    return client_report_package.utc_time(value)


def firmware(value):
    if not isinstance(value, str) or not FIRMWARE.fullmatch(value):
        raise ValueError("unexpected firmware version")
    return value


def enum(value, allowed):
    if value not in allowed:
        raise ValueError("unreviewed value")
    return value


def display(value):
    if not isinstance(value, str) or not DISPLAY_TEXT.fullmatch(value):
        raise ValueError("unexpected display text")
    return value


def response(text, name):
    """A response code whose name agrees with the reviewed table."""
    value = hex_integer(text)
    if RESPONSES.get(value) != name:
        raise ValueError("unexpected response name")
    return code(value)


def parsed_response(pattern, text):
    match = pattern.fullmatch(text) if isinstance(text, str) else None
    if not match:
        raise ValueError("unexpected response text")
    return response(match[1], match[2])


def unsigned(payload):
    return int.from_bytes(bytes.fromhex(raw_scalar(payload)), "little")


def codes(values):
    return [code(hex_integer(value)) for value in values]


def grain_steps(text):
    steps = []
    for part in text.split(", "):
        # "1→OK, reads back 6" is one step that the comma splits in two; rejoin it before matching.
        if part.startswith("reads back ") and steps and steps[-1].endswith("→OK"):
            steps[-1] += ", " + part
        else:
            steps.append(part)
    result = []
    for step in steps:
        match = GRAIN_STEP.fullmatch(step)
        if not match:
            raise ValueError("unexpected grain probe step")
        row = {"writtenUnsigned": int(match[1])}
        if match[2]:
            row.update(result="refused", response=response(match[2], match[3]))
        elif match[4]:
            row["result"] = "accepted"
        else:
            row.update(result="accepted_and_read_back", readbackUnsigned=int(match[5]))
        result.append(row)
    return result


def device_info(info):
    keys(info, {"standardVersion", "vendorExtensionID", "vendorExtensionVersion", "vendorExtensionDesc",
                "functionalMode", "operationsSupported", "eventsSupported", "devicePropertiesSupported",
                "captureFormats", "imageFormats", "manufacturer", "model", "deviceVersion", "rawLength"})
    if (info["manufacturer"], info["model"], info["vendorExtensionDesc"]) != ("FUJIFILM", MODEL, "fujifilm.co.jp: 1.0; "):
        raise ValueError("unexpected DeviceInfo identity")
    for entry in info["operationsSupported"]:
        keys(entry, {"code"}, dropped={"name"})
    for entry in info["devicePropertiesSupported"]:
        keys(entry, {"code"})
    return {"datasetBytes": integer(info["rawLength"]), "standardVersion": integer(info["standardVersion"], 0xFFFF),
            "vendorExtensionID": "0x%08X" % hex_integer(info["vendorExtensionID"]),
            "vendorExtensionVersion": integer(info["vendorExtensionVersion"], 0xFFFF),
            "vendorExtensionDesc": info["vendorExtensionDesc"], "functionalMode": integer(info["functionalMode"], 0xFFFF),
            "manufacturer": "FUJIFILM", "model": MODEL, "deviceVersion": firmware(info["deviceVersion"]),
            "operationsSupported": codes(entry["code"] for entry in info["operationsSupported"]),
            "eventsSupported": codes(info["eventsSupported"]),
            "devicePropertiesSupported": codes(entry["code"] for entry in info["devicePropertiesSupported"]),
            "captureFormats": codes(info["captureFormats"]), "imageFormats": codes(info["imageFormats"])}


def settings(entries):
    """Bank settings and the live D1A5 sample, as unsigned integers keyed by property; labels are dropped."""
    bank, live = {}, {}
    for entry in entries:
        keys(entry, {"code", "value"}, dropped={"name", "decoded"})
        prop = hex_integer(entry["code"])
        if prop not in BANK_CODES | {0xD1A5}:
            raise ValueError("unexpected bank property")
        (bank if prop in BANK_CODES else live)[code(prop)] = unsigned(entry["value"])
    return bank, live


def slot_reads(slots):
    keys(slots, {"reads", "assumedSlotCount", "documentedSlotCount", "probedSlotCount", "selectorBeforeRead",
                 "selectorBeforeProbe", "selectorRestored", "readAt"})
    result = {}
    for key in ("assumedSlotCount", "documentedSlotCount", "probedSlotCount", "selectorBeforeRead", "selectorBeforeProbe"):
        if key in slots:
            result[key] = integer(slots[key], 7)
    if "selectorRestored" in slots:
        result["selectorRestored"] = boolean(slots["selectorRestored"])
    if "readAt" in slots:
        result["readUtc"] = utc(slots["readAt"])
    reads = []
    for read in slots["reads"]:
        keys(read, {"slot", "selected", "occupied", "selectError", "properties", "name"})
        row = {"bank": integer(read["slot"], 7), "selected": boolean(read["selected"])}
        if "selectError" in read:
            row["selectResponse"] = parsed_response(SELECT_ERROR, read["selectError"])
        if "name" in read:
            if not isinstance(read["name"], str):
                raise ValueError("expected a bank name string")
            row["nameEmpty"] = read["name"] == ""
        if "occupied" in read:
            row["occupied"] = boolean(read["occupied"])
        bank, live = settings(read.get("properties", []))
        if bank or live:
            row.update(bankSettingsUnsigned=bank, liveSettingsUnsigned=live)
        reads.append(row)
    result["reads"] = reads
    return result


def descriptor(original):
    keys(original, {"current", "dataType", "enumeration", "factoryDefault", "form", "writable"})
    return {"dataType": enum(original["dataType"], {"UINT16"}), "form": enum(original["form"], {"enumeration"}),
            "enumeration": [integer(value, 0xFFFF) for value in original["enumeration"]],
            "factoryDefault": integer(original["factoryDefault"], 0xFFFF), "current": integer(original["current"], 0xFFFF),
            "writable": boolean(original["writable"])}


def property_sweep(sweep):
    keys(sweep, {"entries", "readOnly", "slot"})
    entries = []
    for entry in sweep["entries"]:
        keys(entry, {"code", "value", "valueError", "descriptor", "descriptorError"}, dropped={"name", "decoded"})
        prop = hex_integer(entry["code"])
        row = {"property": code(prop)}
        if "valueError" in entry:
            row["valueResponse"] = parsed_response(VALUE_ERROR, entry["valueError"])
        else:
            payload = entry["value"]
            if prop in SCALAR_CODES:
                row["valueUnsigned"] = unsigned(payload)
            elif prop == 0xD18D and isinstance(payload, str) and payload.lower() in EMPTY_NAME_PAYLOADS:
                row["emptyNameHex"] = payload.lower()
            else:
                # A bank name read back as a PTP string: never copied, not even its length.
                row["valueOmitted"] = True
        if "descriptorError" in entry:
            row["descriptorResponse"] = parsed_response(DESCRIPTOR_ERROR, entry["descriptorError"])
        if "descriptor" in entry:
            row["descriptor"] = descriptor(entry["descriptor"])
        entries.append(row)
    return {"bank": integer(sweep["slot"], 7), "readOnly": boolean(sweep["readOnly"]), "entries": entries}


def push(original):
    keys(original, {"at", "kind", "slot", "outcome", "baselineOnly", "slotWasEmpty", "selectorReadBack", "nameWritten",
                    "firmwareVersion", "modelID", "clampedFields", "fields", "slotBefore"},
         dropped={"nameBefore", "nameApplied"})
    if original["modelID"] != MODEL or original["clampedFields"]:
        raise ValueError("unexpected push record")
    row = {"recordedUtc": utc(original["at"]), "bank": integer(original["slot"], 7),
           "kind": enum(original.get("kind", "push"), {"push", "restore"}),
           "outcome": enum(original["outcome"], {"applied", "partiallyApplied"}),
           "firmware": firmware(original["firmwareVersion"]), "nameWritten": boolean(original["nameWritten"])}
    for source, target in (("baselineOnly", "baselineOnly"), ("slotWasEmpty", "bankWasEmpty")):
        if source in original:
            row[target] = boolean(original[source])
    if "selectorReadBack" in original:
        row["selectorReadBack"] = integer(original["selectorReadBack"], 7)
    for source, target in (("nameBefore", "nameBeforeEmpty"), ("nameApplied", "nameAppliedEmpty")):
        if source in original:
            if not isinstance(original[source], str):
                raise ValueError("expected a name string")
            row[target] = original[source] == ""
    fields = []
    for field in original["fields"]:
        keys(field, {"code", "outcome", "responseCode", "wrote", "isRecipeField"}, dropped={"name"})
        prop = hex_integer(field["code"])
        if prop not in BANK_CODES | {0xD1A5}:
            raise ValueError("unexpected pushed property")
        entry = {"property": code(prop), "outcome": enum(field["outcome"], {"written", "rejected"}),
                 "writtenUnsigned": unsigned(field["wrote"]), "isRecipeField": boolean(field["isRecipeField"])}
        if "responseCode" in field:
            entry["response"] = code(hex_integer(field["responseCode"]))
        fields.append(entry)
    row["fields"] = fields
    if "slotBefore" in original:
        row["bankBeforeUnsigned"], row["liveBeforeUnsigned"] = settings(
            {"code": key, "value": value} for key, value in original["slotBefore"].items())
    return row


def comparison(original):
    keys(original, {"checkedAt", "filmSimulation", "rows", "slot", "verdict"}, dropped={"name"})
    rows = []
    for row in original["rows"]:
        keys(row, {"appShowed", "differs", "field", "cameraShows"})
        entry = {"field": enum(row["field"], COMPARISON_FIELDS), "clientShowed": display(row["appShowed"]),
                 "differs": boolean(row["differs"])}
        if "cameraShows" in row:
            entry["ownerReportedCamera"] = display(row["cameraShows"])
        rows.append(entry)
    return {"bank": integer(original["slot"], 7), "checkedUtc": utc(original["checkedAt"]),
            "filmSimulation": display(original["filmSimulation"]),
            "verdict": enum(original["verdict"], {"matches", "differs"}), "rows": rows}


def write_pass(original):
    keys(original, {"backup", "consentAt", "restores", "trials"})
    keys(original["backup"], {"savedAt"}, dropped={"activity"})
    trials = []
    for trial in original["trials"]:
        keys(trial, {"menuComparison", "outcome", "persistence", "photoMatchesRecipe", "pushedAt", "recipe", "slot"},
             dropped={"recipeName"})
        persistence = keys(trial["persistence"], {"checkedAt", "nameHolds", "persisted"})
        trials.append({"bank": integer(trial["slot"], 7), "recipe": enum(trial["recipe"], {"mono"}),
                       "pushedUtc": utc(trial["pushedAt"]), "outcome": enum(trial["outcome"], {"applied", "partiallyApplied"}),
                       "persistence": {"checkedUtc": utc(persistence["checkedAt"]),
                                       "persisted": boolean(persistence["persisted"]),
                                       "nameHolds": boolean(persistence["nameHolds"])},
                       "photoMatchesRecipe": enum(trial["photoMatchesRecipe"], {"yes", "no"}),
                       "menuComparison": comparison(trial["menuComparison"])})
    restores = []
    for restore in original["restores"]:
        keys(restore, {"outcome", "slot"})
        restores.append({"bank": integer(restore["slot"], 7), "outcome": enum(restore["outcome"], {"applied"})})
    return {"consentUtc": utc(original["consentAt"]), "backupSavedUtc": utc(original["backup"]["savedAt"]),
            "trials": trials, "restores": restores}


def guided_test(original):
    keys(original, {"wave", "startedAt", "updatedAt", "outcome", "outcomeStep", "transport", "stepsCompleted", "identity",
                    "propertyReport", "grainProbe", "develop", "profileHarvest", "slotComparisons", "writePass"},
         dropped={"sessionID"})
    row = {"wave": integer(original["wave"], 99), "startedUtc": utc(original["startedAt"]),
           "updatedUtc": utc(original["updatedAt"]), "outcome": enum(original["outcome"], {"completed", "sentEarly"}),
           "transport": enum(original["transport"], {"usb"}),
           "stepsCompleted": [enum(step, STEPS) for step in original["stepsCompleted"]]}
    if "outcomeStep" in original:
        row["outcomeStep"] = enum(original["outcomeStep"], STEPS)
    if "identity" in original:
        identity = keys(original["identity"], {"appShowedModelID", "badge", "confirmed", "identification"},
                        dropped={"appShowedProductName"})
        row["identity"] = {"clientShowedModel": enum(identity["appShowedModelID"], {MODEL}),
                           "identification": enum(identity["identification"], {"exact"}),
                           "ownerConfirmed": boolean(identity["confirmed"]), "badge": enum(identity["badge"], BADGES)}
    if "propertyReport" in original:
        report = keys(original["propertyReport"], {"count", "readOnly", "slot", "state"})
        row["propertyReport"] = {"bank": integer(report["slot"], 7), "readOnly": boolean(report["readOnly"]),
                                 "count": integer(report["count"], 99), "state": enum(report["state"], {"ran"})}
    if "grainProbe" in original:
        probe = keys(original["grainProbe"], {"count", "detail", "slot", "state"})
        entry = {"state": enum(probe["state"], {"ran", "notWritable"})}
        if probe["state"] == "ran":
            entry.update(bank=integer(probe["slot"], 7), count=integer(probe["count"], 99), steps=grain_steps(probe["detail"]))
        else:
            entry["detail"] = DETAILS[probe["detail"]]
        row["grainProbe"] = entry
    if "develop" in original:
        develop = keys(original["develop"], {"detail", "state"})
        row["develop"] = {"state": enum(develop["state"], {"notWritable"}), "detail": DETAILS[develop["detail"]]}
    if "profileHarvest" in original:
        harvest = keys(original["profileHarvest"], {"detail", "state"})
        match = HARVEST_DETAIL.fullmatch(harvest["detail"])
        if not match:
            raise ValueError("unexpected profile harvest detail")
        row["profileHarvest"] = {"state": enum(harvest["state"], {"ran"}), "profileBytes": int(match[1]),
                                 "tableOffset": int(match[2], 16)}
    if "slotComparisons" in original:
        row["bankComparisons"] = [comparison(entry) for entry in original["slotComparisons"]]
    if "writePass" in original:
        row["writePass"] = write_pass(original["writePass"])
    return row


def profile_header(text):
    lines = text.split("\n") if isinstance(text, str) else []
    data = b""
    for offset, line in enumerate(lines):
        match = PROFILE_HEAD_LINE.fullmatch(line)
        if not match or int(match[1], 16) != 16 * offset:
            raise ValueError("unexpected profile header dump")
        data += bytes.fromhex(match[2])
    if len(data) != 64:
        raise ValueError("expected the first 64 profile bytes")
    return data


def profile_harvest(original):
    keys(original, {"at", "declaredParams", "firmwareVersion", "layoutBase", "layoutDiagnostic", "modelID",
                    "profileBeforeUpload", "profileHead", "profileLength", "rafBytes", "uploadCreatedObject", "uploadOutcome"})
    if original["modelID"] != MODEL:
        raise ValueError("unexpected profile harvest model")
    header = profile_header(original["profileHead"])
    count = header[2]
    iop = header[3:3 + 2 * count].decode("utf-16-le")
    lines = original["layoutDiagnostic"].split("\n")
    head = HARVEST_HEAD.fullmatch(lines[0])
    if not head or head[3] != iop or int(head[1]) != original["profileLength"] or int(head[2]) != original["declaredParams"]:
        raise ValueError("profile harvest diagnostic disagrees with its record")
    candidates = []
    for line in lines[1:]:
        match = HARVEST_CANDIDATE.fullmatch(line)
        if not match:
            raise ValueError("unexpected layout candidate")
        candidates.append({"tableOffset": int(match[1], 16), "dynamicRangeCell": int(match[2]),
                           "filmSimulationShown": display(match[3]), "score": int(match[4]),
                           "verdict": "accepted" if match[5] == "OK" else "rejected"})
    return {"recordedUtc": utc(original["at"]), "firmware": firmware(original["firmwareVersion"]),
            "profileBeforeUploadResponse": parsed_response(PROFILE_ERROR, original["profileBeforeUpload"]),
            "rafBytes": integer(original["rafBytes"]), "uploadOutcome": enum(original["uploadOutcome"], {"accepted"}),
            "uploadCreatedObject": boolean(original["uploadCreatedObject"]),
            "profileBytes": integer(original["profileLength"]), "numParams": integer(original["declaredParams"], 99),
            "tableOffset": integer(original["layoutBase"], 0xFFFF), "iopCode": iop,
            "first64BytesHex": header.hex(), "canonicalTableOffset": int(head[4], 16), "tailTableOffset": int(head[5], 16),
            "layoutCandidates": candidates}


def note(text):
    for pattern, build in NOTES:
        match = pattern.fullmatch(text) if isinstance(text, str) else None
        if match:
            return build(match)
    raise ValueError("unreviewed client note")


def client_records(original):
    """The client's own derived records, allowlisted. They are its interpretation, not camera responses."""
    return {"app": {"version": enum(original["app"]["version"], {"1.0"}),
                    "build": str(integer(int(original["app"]["build"]), 999)),
                    "channel": enum(original["app"]["channel"], {"testflight"})},
            "deviceInfo": device_info(original["deviceInfo"]),
            "bankReads": slot_reads(original["slots"]),
            "propertySweep": property_sweep(original["propertySweep"]),
            "unsupportedProperties": codes(original["unsupportedPropertyCodes"]),
            "pushes": [push(entry) for entry in original.get("pushes", [])],
            "guidedTests": [guided_test(entry) for entry in original["guidedTests"]],
            "profileHarvests": [profile_harvest(entry) for entry in original.get("profileHarvests", [])],
            "notes": [note(entry) for entry in original["notes"]]}


def transaction(rows, sequence, operation, prop=None, response_code="0x2001"):
    """One reviewed source row, checked before a finding cites it."""
    entry = rows[sequence]
    if entry["operation"] != operation or (prop is not None and entry["parameters"] != [prop]) or \
            (response_code is not None and entry.get("response") != response_code):
        raise ValueError("unexpected reviewed row %d" % sequence)
    return entry


def scalar(entry, direction):
    payload = entry.get(direction + "Data")
    if payload is None or entry.get(direction + "DataLength") != len(payload) // 2:
        raise ValueError("a reviewed scalar lacks its complete bytes")
    return unsigned(payload)


def bank_pass(rows, first_select, banks=range(1, 7)):
    """A reviewed select-and-read pass: per bank, the selector write and readback, the name's form, and the 24 block
    reads in code order, each checked before it is cited. The client strides 27 rows per bank."""
    result = []
    for index, bank in enumerate(banks):
        sequence = first_select + 27 * index
        if scalar(transaction(rows, sequence, "0x1016", "0xD18C"), "out") != bank or \
                scalar(transaction(rows, sequence + 1, "0x1015", "0xD18C"), "in") != bank:
            raise ValueError("expected bank %d selected and read back" % bank)
        name = (transaction(rows, sequence + 2, "0x1015", "0xD18D").get("inData") or "").lower()
        values = {code(prop): scalar(transaction(rows, sequence + 3 + offset, "0x1015", code(prop)), "in")
                  for offset, prop in enumerate(range(0xD18E, 0xD1A6))}
        live = values.pop("0xD1A5")
        result.append({"bank": bank, "selectSequence": sequence, "readSequences": [sequence + 3, sequence + 26],
                       "nameForm": "empty:" + name if name in EMPTY_NAME_PAYLOADS else "named_contents_omitted",
                       "bankSettingsUnsigned": values, "liveD1A5Unsigned": live})
    return result


def block_reads(rows, first):
    values = {code(prop): scalar(transaction(rows, first + offset, "0x1015", code(prop)), "in")
              for offset, prop in enumerate(range(0xD18E, 0xD1A6))}
    return values, values.pop("0xD1A5")


def bank_write(rows, select):
    """A reviewed push or restore: the select and its readback, the 24 block reads, the name read and write, the setting
    writes in order, and the 24 readback reads. Readbacks that differ from what was written are listed, not hidden."""
    bank = scalar(transaction(rows, select, "0x1016", "0xD18C"), "out")
    if scalar(transaction(rows, select + 1, "0x1015", "0xD18C"), "in") != bank:
        raise ValueError("expected the bank selected and read back")
    before, live_before = block_reads(rows, select + 2)
    name = (transaction(rows, select + 26, "0x1015", "0xD18D").get("inData") or "").lower()
    name_write = transaction(rows, select + 27, "0x1016", "0xD18D")
    written = (name_write.get("outData") or "").lower()
    writes, sequence = [], select + 28
    while rows[sequence]["operation"] == "0x1016":
        entry = rows[sequence]
        prop = hex_integer(entry["parameters"][0])
        if prop not in BANK_CODES | {0xD1A5}:
            raise ValueError("unexpected write in a reviewed push")
        writes.append({"sequence": sequence, "property": code(prop), "writtenUnsigned": scalar(entry, "out"),
                       "response": entry["response"], "durationMs": integer(entry["durationMs"])})
        sequence += 1
    after, live_after = block_reads(rows, sequence)
    return {"bank": bank, "selectSequence": select, "beforeReadSequences": [select + 2, select + 25],
            "bankBeforeUnsigned": before, "liveD1A5BeforeUnsigned": live_before,
            "nameRead": {"sequence": select + 26,
                         "form": "empty:" + name if name in EMPTY_NAME_PAYLOADS else "named_contents_omitted"},
            "nameWrite": {"sequence": select + 27, "response": name_write["response"],
                          "durationMs": integer(name_write["durationMs"]),
                          "form": "empty:" + written if written in EMPTY_NAME_PAYLOADS else "name_contents_omitted"},
            "writes": writes, "afterReadSequences": [sequence, sequence + 23],
            "bankAfterUnsigned": after, "liveD1A5AfterUnsigned": live_after,
            "acceptedWritesReadBackDifferently": [
                {"property": row["property"], "writtenUnsigned": row["writtenUnsigned"],
                 "readbackUnsigned": after.get(row["property"], live_after)}
                for row in writes if row["response"] == "0x2001"
                and after.get(row["property"], live_after) != row["writtenUnsigned"]]}


def upload_and_profile(rows, records, observed, first):
    """A reviewed upload at rows first to first+5: the refused profile read, a handle list, SendObjectInfo and SendObject,
    a handle list again, and the profile read after it, with the client's harvest record checked against the trace."""
    transaction(rows, first, "0x1015", "0xD185", "0x2002")
    objects = {row["sequence"]: row for row in observed["objectOperations"]}
    steps = [objects.get(first + offset, {}) for offset in range(1, 5)]
    if [step.get("opcode") for step in steps] != ["0x1007", "0x900C", "0x900D", "0x1007"] or \
            any(step["response"] != "0x2001" for step in steps):
        raise ValueError("expected a handle list, one upload and a handle list")
    profile = transaction(rows, first + 5, "0x1015", "0xD185")
    harvest, = records["profileHarvests"]
    upload = steps[2]
    if (harvest["profileBytes"], harvest["rafBytes"]) != (profile["inDataLength"], upload["bytesSent"]):
        raise ValueError("the client's harvest record disagrees with the trace")
    seconds = upload["durationMs"] / 1000
    return {"profileBeforeUpload": {"sequence": first, "response": "0x2002"},
            "handlesBeforeUpload": {"sequence": first + 1, "handleCount": steps[0]["handleCount"]},
            "sendObjectInfo": {"sequence": first + 2, "response": "0x2001", "payload": "omitted; it names the file"},
            "sendObject": {"sequence": first + 3, "response": "0x2001", "bytesSent": upload["bytesSent"],
                           "durationMs": upload["durationMs"],
                           "derivedRate": {"MiBPerSecond": round(upload["bytesSent"] / seconds / 2 ** 20, 2),
                                           "MBPerSecond": round(upload["bytesSent"] / seconds / 10 ** 6, 2)}},
            "handlesAfterUpload": {"sequence": first + 4, "handleCount": steps[3]["handleCount"]},
            "profileAfterUpload": {"sequence": first + 5, "response": "0x2001", "bytes": profile["inDataLength"]},
            "clientProfileHarvest": {"basis": "the client's harvest record; the ledger omits the profile payload",
                                     "numParams": harvest["numParams"], "iopCode": harvest["iopCode"],
                                     "tableOffset": harvest["tableOffset"], "uploadCreatedObject": harvest["uploadCreatedObject"],
                                     "first64BytesHex": harvest["first64BytesHex"],
                                     "layoutCandidates": harvest["layoutCandidates"]}}


def priority_history(records):
    """The client's D-Range Priority comparison rows, with the Dynamic Range row beside each, and every D191 refusal its
    push records hold. Push and comparison records carry forward from report to report, so each keeps its own time."""
    comparisons = []
    for test in records["guidedTests"]:
        for entry in test.get("bankComparisons", []):
            rows = {row["field"]: row for row in entry["rows"]}
            if "D-Range Priority" in rows:
                row = dict(rows["D-Range Priority"])
                del row["field"]
                comparisons.append({"bank": entry["bank"], "checkedUtc": entry["checkedUtc"], "dRangePriority": row,
                                    "dynamicRangeClientShowed": rows["Dynamic Range"]["clientShowed"]})
    refusals = [{"recordedUtc": push["recordedUtc"], "bank": push["bank"], "outcome": push["outcome"],
                 "response": field.get("response")}
                for push in records["pushes"] for field in push["fields"]
                if field["property"] == "0xD191" and field["outcome"] == "rejected"]
    return comparisons, refusals


def observations(original):
    """Mechanical observations over the trace; every number is recomputable from transactions.jsonl or the original."""
    rows = original["transactions"]
    addressed, selector, writes, objects, profile = None, [], [], [], []
    descriptors = collections.defaultdict(collections.Counter)
    for entry in rows:
        opcode = hex_integer(entry["operation"])
        params = [hex_integer(value) for value in entry["parameters"]]
        prop = params[0] if opcode in client_report_package.PROPERTY_OPERATIONS else None
        result = entry.get("response")
        sequence = integer(entry["sequence"])
        if opcode == 0x1014:
            descriptors[code(prop)][result] += 1
        elif prop == 0xD18C:
            value = scalar(entry, "out" if opcode == 0x1016 else "in") if result == "0x2001" or opcode == 0x1016 else None
            selector.append({"sequence": sequence, "operation": "write" if opcode == 0x1016 else "read",
                             "valueUnsigned": value, "response": result})
            if result == "0x2001":
                addressed = value
        elif opcode == 0x1016 and prop in BANK_CODES | {0xD1A5}:
            writes.append({"sequence": sequence, "addressedBank": addressed, "property": code(prop),
                           "writtenUnsigned": scalar(entry, "out"), "response": result,
                           "durationMs": integer(entry["durationMs"])})
        elif opcode == 0x1016 and prop == 0xD18D:
            payload = entry.get("outData")
            form = payload.lower() if isinstance(payload, str) and payload.lower() in EMPTY_NAME_PAYLOADS else None
            writes.append({"sequence": sequence, "addressedBank": addressed, "property": "0xD18D",
                           "nameForm": "empty:" + form if form else "name_omitted", "response": result,
                           "durationMs": integer(entry["durationMs"])})
        elif prop == 0xD185 and opcode == 0x1015:
            profile.append({"sequence": sequence, "response": result, "durationMs": integer(entry["durationMs"]),
                            "bytes": integer(entry["inDataLength"]) if result == "0x2001" else None})
        elif opcode in (0x1007, 0x900C, 0x900D):
            row = {"sequence": sequence, "opcode": code(opcode), "response": result,
                   "durationMs": integer(entry["durationMs"])}
            if opcode == 0x1007:
                payload = entry.get("inData")
                if payload is None or entry.get("inDataLength") != len(payload) // 2 or len(payload) < 8:
                    raise ValueError("a handle list lacks its count")
                # The array count leads the dataset; the handles themselves are never copied.
                row["handleCount"] = int.from_bytes(bytes.fromhex(payload[:8]), "little")
            elif opcode == 0x900D:
                row["bytesSent"] = integer(entry["outDataLength"])
            objects.append(row)
    accepted = sorted(row["durationMs"] for row in writes if row["response"] == "0x2001" and row["property"] != "0xD18D")
    device_info_rows = [entry for entry in rows if entry["operation"] == "0x1001"]
    return {"getDeviceInfo": [{"sequence": integer(entry["sequence"]), "response": entry.get("response"),
                               "durationMs": integer(entry["durationMs"])} for entry in device_info_rows],
            "selector": selector, "writes": writes,
            "descriptorResponses": {prop: dict(sorted(counts.items())) for prop, counts in sorted(descriptors.items())},
            "conversionProfileReads": profile, "objectOperations": objects,
            "acceptedSettingWriteDurationsMs": ({"count": len(accepted), "minimum": accepted[0],
                                                 "median": accepted[len(accepted) // 2], "maximum": accepted[-1]}
                                                if accepted else None)}


def private_strings(original):
    """Every string in the original that must never reach a public output, with its encoded forms."""
    found = {original["camera"]["serialHash"], original["host"]["deviceIdentifier"]}
    names = {read.get("name", "") for read in original["slots"]["reads"]}
    for entry in original.get("pushes", []):
        names.update((entry.get("nameBefore", ""), entry.get("nameApplied", "")))
    for test in original["guidedTests"]:
        found.add(test["sessionID"])
        names.update(entry.get("name", "") for entry in test.get("slotComparisons", []))
        for trial in test.get("writePass", {}).get("trials", []):
            names.update((trial.get("recipeName", ""), trial["menuComparison"].get("name", "")))
    for entry in original["transactions"]:
        hidden = entry["operation"] == "0x900C" or entry["parameters"] == ["0xD18D"]
        for direction in ("in", "out"):
            payload = entry.get(direction + "Data")
            if hidden and isinstance(payload, str):
                payload = re.match(r"[0-9A-Fa-f]*", payload)[0].lower()
                if payload not in EMPTY_NAME_PAYLOADS:
                    found.add(payload)
    for entry in original["propertySweep"]["entries"]:
        if entry["code"] == "0xD18D" and isinstance(entry.get("value"), str) and \
                entry["value"].lower() not in EMPTY_NAME_PAYLOADS:
            found.add(entry["value"].lower())
    for name in names - {"", MODEL}:
        utf16 = name.encode("utf-16-le").hex()
        found.update((name, json.dumps(name)[1:-1], utf16, utf16 + "0000"))
    return {value.lower() for value in found if isinstance(value, str) and len(value) >= 4}


def check_disclosure(outputs, secrets):
    text = b"".join(outputs.values()).decode("utf-8").lower()
    if any(secret in text for secret in secrets):
        raise ValueError("an output contains a private string from the original")


def build_package(original_bytes, spec, review, exporter_path):
    """Verify the reviewed source before any projection or review is invoked."""
    evidence_id = spec["evidenceId"]
    if not IDENTIFIER.fullmatch(evidence_id):
        raise ValueError("unexpected package identifier")
    if not re.fullmatch(r"[0-9a-f]{40}", spec["sourceRevision"]) or not SOURCE_PATH.fullmatch(spec["sourcePath"]):
        raise ValueError("invalid source revision or path")
    if not re.fullmatch(r"[0-9a-f]{64}", spec["sourceSha256"]):
        raise ValueError("invalid source hash")
    if sha256(original_bytes) != spec["sourceSha256"]:
        raise ValueError("original SHA-256 does not match the reviewed run")
    original = json.loads(original_bytes)
    camera = original["camera"]
    model = camera.get("identifiedModelID")
    if original["reportVersion"] not in REPORT_VERSIONS or camera["productName"] != MODEL or model not in (MODEL, None):
        raise ValueError("unexpected source camera metadata")
    if original["transactionsDropped"] != 0 or len(original["transactions"]) != spec["transactionCount"]:
        raise ValueError("the reviewed trace is one complete client trace")
    ledger = client_report_package.ledger_rows(original["transactions"])
    if [row["sequence"] for row in ledger] != list(range(1, len(ledger) + 1)):
        raise ValueError("the trace's sequence numbers are not contiguous from 1")
    records = client_records(original)
    observed = observations(original)
    rows = {entry["sequence"]: entry for entry in original["transactions"]}
    outputs = {
        "transactions.jsonl": b"".join((json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
                                       for row in ledger),
        "client-records.json": json_bytes({"format": "fuji-owner-client-records-v1", "evidenceId": evidence_id,
                                           "records": records}),
        "findings.json": json_bytes({"format": "fuji-owner-client-report-observations-v1", "evidenceId": evidence_id,
                                     "observations": observed, "reviewed": review(original, rows, records, observed)}),
    }
    secrets = private_strings(original)
    check_disclosure(outputs, secrets)
    firmware_version = firmware(camera["firmwareVersion"])
    manifest = {
        "format": "fuji-owner-client-report-sanitized-package-v1", "evidenceId": evidence_id,
        "evidenceKind": "owner_report_original_sanitized_derivative",
        "source": {"access": "private archive", "archivePath": spec["sourcePath"], "revision": spec["sourceRevision"],
                   "sha256": spec["sourceSha256"], "bytes": len(original_bytes),
                   "reportFormatVersion": original["reportVersion"]},
        "camera": {"model": MODEL, "firmware": firmware_version, "provenance": "owner_report",
                   "identification": enum(camera["identification"], {"exact", "unknown"}), "usbMode": None},
        "host": {"client": "the maintainers' iOS client, TestFlight build " + records["app"]["build"],
                 "operatingSystem": "iOS or iPadOS", "systemVersion": enum(original["host"]["systemVersion"], {"26.3"}),
                 "deviceModel": "omitted", "transport": "ImageCaptureCore"},
        "conditions": {"autoUpdateCustomSetting": "unknown", "lensPresent": None, "iso": None, "imageFormat": "unknown"},
        "time": {"reportGeneratedUtc": utc(original["generatedAt"]), "reportUpdatedUtc": utc(original["updatedAt"]),
                 "identifierClock": "the report's updatedAt in the owner's local time, UTC-4, which the archive file names use",
                 "perTransactionTimestamps": "absent", "connectionIds": "omitted"},
        "coverage": {"sourceArray": "transactions", "traceScope": "the client's trace of its connection at export",
                     "sourceEntries": len(ledger), "retainedEntries": len(ledger), "droppedEntries": 0,
                     "sourceTransactionsDropped": 0,
                     "outcomes": dict(sorted(collections.Counter(row["outcome"] for row in ledger).items())),
                     "scalarPayloadsRetained": sum(key in row for row in ledger for key in ("dataInLE", "dataOutLE")),
                     "payloadFieldsOmitted": sum(len(row.get("omittedPayloads", [])) for row in ledger),
                     "emptyNamePayloadsRetained": sum(key in row for row in ledger
                                                      for key in ("emptyNameInHex", "emptyNameOutHex")),
                     "clientRecords": {"bankReads": len(records["bankReads"]["reads"]), "pushes": len(records["pushes"]),
                                       "guidedTests": len(records["guidedTests"]),
                                       "profileHarvests": len(records["profileHarvests"]), "notes": len(records["notes"])},
                     "privateStringsChecked": len(secrets), "sourceCaptureCompleteness": "client_trace_only"},
        "interpretation": {"sourceIndex": "zero-based original transactions array index; order preserved",
                           "sequence": "the client's own count within its trace; not a PTP transaction ID",
                           "rawPayloadEncoding": "hexadecimal bytes in source order, little-endian scalar interpretation",
                           "dataPhase": "the bytes the client handed to ImageCaptureCore or received from it; the USB wire is not observed",
                           "responseOrigin": "the response code ImageCaptureCore returned to the client; not an independent bus capture",
                           "durationMs": "host-measured time from handing over the command to its completion",
                           "clientRecords": "the client's own derived records, allowlisted; its interpretation, not camera responses",
                           "ownerReportedCamera": "what the owner entered as the camera's menu reading; not a photograph",
                           "findingNumbers": "unsigned integers unless explicitly labeled; not byte strings"},
        "transform": {"generator": "export.py", "generatorSha256": sha256(Path(exporter_path).read_bytes()),
                      "sharedGenerator": "../owner_report_package.py", "sharedGeneratorSha256": sha256(Path(__file__).read_bytes()),
                      "ledgerModule": "../client_report_package.py",
                      "ledgerModuleSha256": sha256(Path(client_report_package.__file__).read_bytes()),
                      "helperModule": "../bankprobe_package.py",
                      "helperModuleSha256": sha256(Path(bankprobe_package.__file__).read_bytes()),
                      "originalUnchanged": True, "publicSchemaV1Compatible": False, "losslessBackup": False,
                      "payloadAllowlist": [code(value) for value in sorted(SCALAR_CODES)], "maximumPayloadBytes": 4,
                      "omissions": ["serial hash, host device model, guided-test session identifiers and USB identifiers",
                                    "bank and recipe names wherever they occur, and all D18D payloads except the two empty-name encodings (00 and 010000)",
                                    "lengths of every omitted payload",
                                    "DeviceInfo, descriptor, conversion-profile and object payloads in the ledger",
                                    "parameters of operations other than property get, set and describe",
                                    "the client's property labels, free-text notes and messages except reviewed forms parsed into typed fields",
                                    "the backup's share-sheet activity, problem reports, app logs, photographs and JPEGs"],
                      "disclosureCheck": "every output searched for each private string of the original, plain, JSON-escaped and UTF-16 hex",
                      "generatedFacts": "No missing times, conditions, or hardware observations are invented; finding interpretations are labeled."},
        "artifacts": {name: {"sha256": sha256(value), "bytes": len(value)} for name, value in outputs.items()},
    }
    outputs["manifest.json"] = json_bytes(manifest)
    check_disclosure(outputs, secrets)
    return outputs


def package_main(spec, review, exporter_path, argv=None):
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
        outputs = build_package(args.original.read_bytes(), spec, review, exporter_path)
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
