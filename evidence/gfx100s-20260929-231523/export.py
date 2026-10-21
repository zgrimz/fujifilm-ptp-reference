#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import bank_pass, package_main, priority_history, scalar, transaction  # noqa: E402

SPEC = {"evidenceId": "gfx100s-20260929-231523",
        "sourceSha256": "1744358b1c8534ecdf18ef6c459e5a389034168cffbf77c90f97d15f51d697f9",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-29/C1 REPORT WITH DIAGNOSTIC MODE - fuji-cookbook-camera-report-GFX100S-20260929-2309.json",
        "transactionCount": 165}

# The client's D-Range Priority comparisons this report carries: bank, time, what the client showed, whether the owner
# marked the row as differing, and the owner's reading of the camera where they did. Later reports carry these forward.
COMPARISONS = [(1, "2026-09-19T00:53:11Z", "Auto", True, "OFF"), (2, "2026-09-19T00:55:22Z", "Auto", False, None),
               (1, "2026-09-30T02:18:22Z", "Auto", True, "OFF"), (2, "2026-09-30T02:19:58Z", "Off", False, None),
               (1, "2026-09-30T03:15:16Z", "Auto", True, "OFF (yellow)")]
REFUSALS = ["2026-09-19T01:08:59Z", "2026-09-30T02:22:27Z"]
# The selector as the trace's first read finds it, left by the client's previous connection.
INITIAL_SELECTOR = 6
TRAILING = [(165, "0x1015", 6)]


def review(original, rows, records, observed):
    if scalar(transaction(rows, 2, "0x1015", "0xD18C"), "in") != INITIAL_SELECTOR:
        raise ValueError("unexpected selector before the pass")
    banks = bank_pass(rows, 3)
    for sequence, operation, value in TRAILING:
        if scalar(transaction(rows, sequence, operation, "0xD18C"), "out" if operation == "0x1016" else "in") != value:
            raise ValueError("unexpected selector row after the pass")
    if any(entry["operation"] == "0x1016" and entry["parameters"] != ["0xD18C"] for entry in original["transactions"]):
        raise ValueError("the reviewed trace writes only the selector")
    priority = [(bank["bank"], bank["bankSettingsUnsigned"]["0xD191"], bank["bankSettingsUnsigned"]["0xD190"]) for bank in banks]
    if priority != [(1, 0x8000, 0xFFFF), (2, 0, 400)] + [(bank, 0, 100) for bank in range(3, 7)]:
        raise ValueError("expected C1 at D-Range Priority Auto and the other banks off")
    comparisons, refusals = priority_history(records)
    if [(c["bank"], c["checkedUtc"], c["dRangePriority"]["clientShowed"], c["dRangePriority"]["differs"],
         c["dRangePriority"].get("ownerReportedCamera")) for c in comparisons] != COMPARISONS or \
            [(r["recordedUtc"], r["bank"], r["response"]) for r in refusals] != [(at, 1, "0x201C") for at in REFUSALS]:
        raise ValueError("D-Range Priority history differs from the reviewed report")
    return {"bankPass": banks,
            "dRangePriorityInTrace": {"c1ReadSequence": banks[0]["readSequences"][0] + 3, "c1Unsigned": 0x8000,
                                      "c1DynamicRangeUnsigned": 0xFFFF, "otherBanksUnsigned": 0},
            "dRangePriorityHistory": {"basis": "the client's comparison and push records, carried forward from earlier "
                                               "sessions; the owner's camera readings are as entered, not photographs",
                                      "comparisons": comparisons, "d191Refusals": refusals},
            "notEstablished": ["each bank's ISO, which the client did not read",
                               "whether the owner's reported ISO change on C1 was saved to the bank",
                               "the 2026-09-19 session's transactions", "USB mode",
                               "AUTO UPDATE CUSTOM SETTING, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
