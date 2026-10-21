#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import bank_pass, package_main, scalar, transaction, upload_and_profile  # noqa: E402

SPEC = {"evidenceId": "gfx100s-20260917-211657",
        "sourceSha256": "459d958f5023140c9530d9e901f877067c94f28fabddb9cd9da6933a59e12278",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-17/fuji-cookbook-camera-report-GFX100S-20260917-2111.json",
        "transactionCount": 171}

LAYOUT = [(0x1FD, 5, "accepted"), (0x201, 3, "rejected"), (0x1F9, 2, "rejected")]


def review(original, rows, records, observed):
    if scalar(transaction(rows, 2, "0x1015", "0xD18C"), "in") != 6:
        raise ValueError("expected the selector at 6 before the pass")
    banks = bank_pass(rows, 3)
    if any(entry["operation"] == "0x1016" and entry["parameters"] != ["0xD18C"] for entry in original["transactions"]):
        raise ValueError("the reviewed trace writes only the selector")
    upload = upload_and_profile(rows, records, observed, 166)
    harvest = upload["clientProfileHarvest"]
    if (upload["handlesBeforeUpload"]["handleCount"], upload["handlesAfterUpload"]["handleCount"],
            upload["sendObject"]["bytesSent"], upload["sendObject"]["durationMs"], upload["profileAfterUpload"]["bytes"],
            harvest["numParams"], harvest["iopCode"], harvest["tableOffset"], harvest["uploadCreatedObject"]) != \
            (0, 0, 208071296, 5392, 621, 28, "FF149502", 0x1FD, False) or \
            [(c["tableOffset"], c["score"], c["verdict"]) for c in harvest["layoutCandidates"]] != LAYOUT:
        raise ValueError("upload or profile differs from the reviewed run")
    return {"bankPass": banks, "conversion": upload,
            "notEstablished": ["the RAF's contents and as-shot settings beyond the profile header", "USB mode",
                               "AUTO UPDATE CUSTOM SETTING, ISO, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
