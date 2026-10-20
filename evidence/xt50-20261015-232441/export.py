#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export selected observations from one reviewed, hash-pinned private run."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bankprobe_package import build_package, package_main, integer, hex_integer, code, trial


SPEC = {
    "evidenceId": "xt50-20261015-232441",
    "sourceSha256": "eebcebf1f9613e80cc6939c302ff5f2f8ec69abb91131a55efe8e00bb9208975",
    "imageFormat": "varied_by_prompted_subtest",
}
TRANSCRIPT_SHA256 = "df4f55cd6bddeb12da79ce0e82fb06a18fd06adb089287bcd8d25566d499c9d1"
TRANSCRIPT_PATH = "hardware-runs/bankprobe-x-t50-2026-10-15/transcripts/bankprobe-20261015-232441.txt"


def changed_fields(rows):
    result = []
    for prop, before, after in rows:
        prop_number = hex_integer(prop)
        if not 0xD18E <= prop_number <= 0xD1A4:
            raise ValueError("unexpected comparison property")
        result.append({"property": code(prop_number),
                       "beforeUnsigned": integer(before, 0xFFFF),
                       "afterUnsigned": integer(after, 0xFFFF)})
    return result


def menu_rows(rows, labels, properties):
    if len(rows) != len(labels):
        raise ValueError("unexpected menu observation count")
    result = []
    for index, (row, label, prop) in enumerate(zip(rows, labels, properties)):
        expected = row["expected"]
        result.append({"sourceDetailIndex": index, "promptedMenuLabel": label,
                       "property": code(prop), "readUnsigned": integer(row["value"], 0xFFFF),
                       "expectedUnsigned": integer(expected, 0xFFFF) if expected is not None else None,
                       "reportedOtherChanges": changed_fields(row["others"])})
    return result


def ledger_trial(original, write_index, read_index):
    """Project exact scalar rows when an interrupted helper lost its summary."""
    write = original["transactions"][write_index]
    read = original["transactions"][read_index]
    if (write["op"] != "0x1016" or read["op"] != "0x1015"
            or write["params"] != ["0xD18E"] or read["params"] != ["0xD18E"]
            or read["response"] != "0x2001"):
        raise ValueError("partial Image Size trial needs renewed review")
    return {"writeSourceIndex": write_index, "readbackSourceIndex": read_index,
            **trial({"code": 0xD18E, "wrote": int.from_bytes(bytes.fromhex(write["data_out"]), "little"),
                     "rc": hex_integer(write["response"]),
                     "read": int.from_bytes(bytes.fromhex(read["data_in"]), "little")})}


def build_findings(original):
    findings = original["findings"]
    tests = ["d1a3-meaning", "wb-sweep", "imagesize-sweep", "imagequality-sweep",
             "d1a5-live", "selector-reset", "heif-scope", "iso-threshold",
             "d18e-gates", "no-name-control"]
    if [finding["test"] for finding in findings] != tests:
        raise ValueError("unexpected source finding order")
    result = [
        {"sourceFindingIndex": 0, "kind": "prompted_lmo_color_space",
         "rows": menu_rows(findings[0]["detail"],
                           ["LMO ON", "LMO OFF", "Adobe RGB", "sRGB"],
                           [0xD1A3, 0xD1A3, 0xD1A4, 0xD1A4])},
        {"sourceFindingIndex": 1, "kind": "prompted_white_balance",
         "rows": menu_rows(findings[1]["detail"],
                           ["AUTO WHITE PRIORITY", "AUTO AMBIENCE PRIORITY", "UNDERWATER", "SHADE",
                            "FLUORESCENT LIGHT 1", "INCANDESCENT", "AUTO", "CUSTOM 1"], [0xD199] * 8)},
    ]
    size_labels = ["L 16:9", "L 1:1", "M 3:2", "S 3:2", "L 3:2"]
    if len(findings[2]["detail"]) != len(size_labels):
        raise ValueError("unexpected Image Size observation count")
    result.append({"sourceFindingIndex": 2, "kind": "prompted_bank_and_live_image_size",
                   "rows": [{"sourceDetailIndex": index, "promptedMenuLabel": label,
                             "bankD18EUnsigned": integer(row["d18e"], 0xFFFF),
                             "expectedUnsigned": integer(row["expected"], 0xFFFF),
                             "liveD1A5Unsigned": integer(row["d1a5"], 0xFFFF)}
                            for index, (row, label) in enumerate(zip(findings[2]["detail"], size_labels))]})
    result.append({"sourceFindingIndex": 3, "kind": "prompted_image_quality",
                   "rows": menu_rows(findings[3]["detail"],
                                     ["FINE", "NORMAL", "FINE + RAW", "NORMAL + RAW", "RAW"], [0xD18F] * 5)})
    live = findings[4]["detail"]
    if len(live["d18e"]) != 2 or len(live["d1a5"]) != 2 or live["camera_showed"] != "1:1":
        raise ValueError("live-size observation needs renewed review")
    result.append({"sourceFindingIndex": 4, "kind": "live_image_size_observation",
                   "samples": [{"selectedBank": bank, "sourceDetailArrayIndex": index,
                                "bankD18EUnsigned": integer(live["d18e"][index], 0xFFFF),
                                "liveD1A5Unsigned": integer(live["d1a5"][index], 0xFFFF)}
                               for index, bank in enumerate((7, 6))],
                   "write": {"sourcePointer": "/findings/4/detail/write", **trial(live["write"])},
                   "operatorObservation": {"sourcePointer": "/findings/4/detail/camera_showed",
                                           "reportedMenuAspectRatio": "1:1"}})
    selector = findings[5]["detail"]
    if selector["body_before"] != "7" or set(selector["sims"]) != {"6", "7"}:
        raise ValueError("selector observation needs renewed review")
    result.append({"sourceFindingIndex": 5, "kind": "selector_observation",
                   "reportedBodyBankBefore": {"sourcePointer": "/findings/5/detail/body_before", "bank": 7},
                   "values": {key: integer(selector[key], 0xFFFF)
                              for key in ("on_connect", "after_cable", "after_change", "sim_noselect")},
                   "comparisonBankFilmSimulations": [
                       {"sourcePointer": "/findings/5/detail/sims/" + str(bank),
                        "selectedBank": bank, "readUnsigned": integer(selector["sims"][str(bank)], 0xFFFF)}
                       for bank in (7, 6)]})
    format_rows = []
    for source_key, image_format, bank in (("heif_C7", "HEIF", 7), ("heif_C6", "HEIF", 6),
                                          ("jpeg_C7", "JPEG", 7), ("jpeg_C6", "JPEG", 6)):
        format_rows.append({"sourcePointer": "/findings/6/detail/" + source_key,
                            "promptedCameraFormat": image_format, "selectedBank": bank,
                            **trial(findings[6]["detail"][source_key])})
    result.append({"sourceFindingIndex": 6, "kind": "prompted_format_bank_comparison", "rows": format_rows})
    iso_rows = []
    for source_key, iso in (("125 (base)", 125), ("250", 250), ("500", 500)):
        for index, row in enumerate(findings[7]["detail"][source_key]):
            iso_rows.append({"sourcePointer": "/findings/7/detail/" + source_key + "/" + str(index),
                             "promptedIso": iso, **trial(row)})
    result.append({"sourceFindingIndex": 7, "kind": "prompted_iso_dynamic_range_trials", "rows": iso_rows})
    if findings[8]["detail"] is not None:
        raise ValueError("unexpected partial Image Size summary")
    result.append({"sourceFindingIndex": 8, "kind": "interrupted_image_size_gate_test",
                   "sourceDetailRecorded": False,
                   "interpretation": "partial_trials_recovered_from_ledger_and_reviewed_transcript",
                   "transcriptContext": {"sourceArtifact": "transcripts/bankprobe-20261015-232441.txt",
                                         "sha256": TRANSCRIPT_SHA256,
                                         "archivePath": TRANSCRIPT_PATH,
                                         "verification": "reviewed_separately_not_reprocessed_by_this_exporter"},
                   "rows": [{"promptedDigitalTeleConverter": condition,
                             "transcriptPromptLine": prompt_line, **ledger_trial(original, write_index, read_index)}
                            for condition, prompt_line, write_index, read_index in
                            (("on", 625, 1562, 1563), ("off", 632, 1571, 1572))],
                   "hdrTrialRecorded": False,
                   "hdrPromptTranscriptLine": 639})
    control = findings[9]["detail"]
    no_name_window = original["transactions"][1607:1620]
    name_writes = sum(row.get("op") == "0x1016" and row.get("params") == ["0xD18D"]
                      for row in no_name_window)
    result.append({"sourceFindingIndex": 9, "kind": "no_name_write_control",
                   "property": "0xD192", "initialUnsigned": integer(control["original"], 0xFFFF),
                   "writtenUnsigned": integer(control["wrote"], 0xFFFF),
                   "postProcedureReadUnsigned": integer(control["after"], 0xFFFF),
                   "initialReadSourceIndex": 1587, "writeSourceIndex": 1607,
                   "immediateReadSourceIndex": 1608, "postProcedureReadSourceIndex": 1619,
                   "nameWritesBetweenWriteAndPostProcedureRead": name_writes})
    return result


def export_bundle(original_bytes):
    return build_package(original_bytes, SPEC, build_findings, __file__)


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, build_findings, __file__))
