#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute the bank-write timing figures from the published client-trace ledgers. No camera access, no originals.

Every package whose ledger carries host-measured `durationMs` is read: the maintainers' X-T50 client traces and the
GFX100S owner traces. A trace that is an exact prefix of another trace of the same body is a later export of the same
connection and is counted once. A write at or above SLOW_MS is counted as slow; the published traces leave a gap of
more than 100 ms on both sides of it.
"""
import argparse
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SLOW_MS = 200
NAME, LIVE_IMAGE_SIZE, WHITE_BALANCE, PROFILE = 0xD18D, 0xD1A5, 0xD199, 0xD185
BANK_SETTINGS = range(0xD18E, 0xD1A5)


def traces(root=ROOT):
    """(evidence id, model, ledger rows) for every published client trace, without traces repeated by a later export."""
    found = []
    for manifest_path in sorted(Path(root, "evidence").rglob("manifest.json")):
        ledger_path = manifest_path.with_name("transactions.jsonl")
        if not ledger_path.exists():
            continue
        rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        if rows and all("durationMs" in row for row in rows):
            manifest = json.loads(manifest_path.read_text())
            found.append((manifest["evidenceId"], manifest["camera"]["model"], rows))
    return [(evidence_id, model, rows) for evidence_id, model, rows in found
            if not any(other_model == model and len(other) > len(rows) and other[:len(rows)] == rows
                       for _, other_model, other in found)]


def summary(values):
    values = sorted(values)
    if not values:
        return None
    fast = [value for value in values if value < SLOW_MS]
    slow = [value for value in values if value >= SLOW_MS]
    return {"count": len(values), "median": statistics.median(values),
            "fast": {"count": len(fast), "minimum": fast[0], "median": statistics.median(fast), "maximum": fast[-1],
                     "p10": fast[len(fast) // 10], "p90": fast[9 * len(fast) // 10]} if fast else None,
            "slow": {"count": len(slow), "share": round(len(slow) / len(values), 3), "minimum": slow[0],
                     "maximum": slow[-1]} if slow else None}


def timing(root=ROOT):
    by_model = {}
    for evidence_id, model, rows in traces(root):
        model_rows = by_model.setdefault(model, {"traces": [], "name": [], "settings": [], "whiteBalance": [], "live": [],
                                                 "reads": []})
        model_rows["traces"].append(evidence_id)
        for row in rows:
            prop = row.get("parameters", [None])[0]
            if row["opcode"] == "0x1015" and prop != PROFILE:
                model_rows["reads"].append(row["durationMs"])
            if row["opcode"] != "0x1016" or row["response"] != "0x2001":
                continue
            if prop == NAME:
                model_rows["name"].append(row["durationMs"])
            elif prop == LIVE_IMAGE_SIZE:
                model_rows["live"].append(row["durationMs"])
            elif prop in BANK_SETTINGS:
                model_rows["settings"].append(row["durationMs"])
                if prop == WHITE_BALANCE:
                    model_rows["whiteBalance"].append(row["durationMs"])
    return {model: {"traces": sorted(values["traces"]), "nameWrites": summary(values["name"]),
                    "bankSettingWrites": summary(values["settings"]), "whiteBalanceWrites": summary(values["whiteBalance"]),
                    "liveImageSizeWrites": summary(values["live"]),
                    "propertyReads": {"count": len(values["reads"]), "maximum": max(values["reads"]),
                                      "atOrAbove100Ms": sum(value >= 100 for value in values["reads"])}}
            for model, values in sorted(by_model.items())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the full summary as JSON")
    args = parser.parse_args(argv)
    result = timing()
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    for model, figures in result.items():
        print("%s: %d traces" % (model, len(figures["traces"])))
        for label, key in (("name writes", "nameWrites"), ("bank-setting writes", "bankSettingWrites"),
                           ("white balance writes", "whiteBalanceWrites"), ("live Image Size writes", "liveImageSizeWrites")):
            figure = figures[key]
            if figure:
                fast, slow = figure["fast"], figure["slow"]
                print("  %-23s %4d accepted; %4d at %d-%d ms (median %s)%s" % (
                    label, figure["count"], fast["count"], fast["minimum"], fast["maximum"], fast["median"],
                    "; %d at %d-%d ms" % (slow["count"], slow["minimum"], slow["maximum"]) if slow else ""))
        reads = figures["propertyReads"]
        print("  %-23s %4d; slowest %d ms; %d at 100 ms or more" % ("property reads", reads["count"], reads["maximum"],
                                                                     reads["atOrAbove100Ms"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
