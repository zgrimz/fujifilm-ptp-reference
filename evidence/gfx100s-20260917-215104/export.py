#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import (bank_pass, bank_write, package_main, scalar, transaction,  # noqa: E402
                                  upload_and_profile)

SPEC = {"evidenceId": "gfx100s-20260917-215104",
        "sourceSha256": "2be55bb14c39ac592a94ebf2f8f36eb9fcc6dd2e5e99f138b6988fbca0823be8",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-17/fuji-cookbook-camera-report-GFX100S-20260917-2111 2.json",
        "transactionCount": 384}


def review(original, rows, records, observed):
    if scalar(transaction(rows, 2, "0x1015", "0xD18C"), "in") != 6:
        raise ValueError("expected the selector at 6 before the pass")
    banks = bank_pass(rows, 3)
    upload = upload_and_profile(rows, records, observed, 166)
    if (upload["sendObject"]["bytesSent"], upload["profileAfterUpload"]["bytes"]) != (208071296, 621):
        raise ValueError("expected the same upload as the 21:16:57 report")
    pushes = [bank_write(rows, select) for select in (172, 243, 314)]
    dr = [[row for row in push["writes"] if row["property"] == "0xD190"][0] for push in pushes]
    if [push["bank"] for push in pushes] != [2, 3, 4] or \
            [(row["writtenUnsigned"], row["response"]) for row in dr] != [(400, "0x2001"), (400, "0x201C"), (400, "0x201C")]:
        raise ValueError("expected DR400 accepted on C2 and refused on C3 and C4")
    before = [push["bankBeforeUnsigned"] for push in pushes]
    if any((values["0xD190"], values["0xD191"]) != (100, 0) for values in before) or \
            [(values["0xD193"], values["0xD194"], values["0xD195"]) for values in before] != \
            [(20, 65526, 7), (0, 0, 6), (0, 0, 6)]:
        raise ValueError("expected DR100 with D-Range Priority off on all three, and differing toning and grain")
    if any(row["property"] in ("0xD191", "0xD1A5") for push in pushes for row in push["writes"]) or \
            any(row["response"] != "0x2001" for push in pushes for row in push["writes"] if row["property"] != "0xD190"):
        raise ValueError("expected every other setting accepted and D191 and D1A5 not written")
    withheld = [note for note in records["notes"] if note["kind"] == "properties_withheld"]
    if [(note["bank"], note["properties"]) for note in withheld] != [(bank, ["0xD191", "0xD1A5"]) for bank in (2, 3, 4)]:
        raise ValueError("expected the client's notes on withholding D191 and D1A5")
    readback = [push["bankAfterUnsigned"]["0xD190"] for push in pushes]
    if readback != [400, 100, 100]:
        raise ValueError("expected DR read back as 400 on C2 and unchanged on C3 and C4")
    return {"bankPass": banks, "conversion": upload,
            "firstRowsShared": {"rows": [1, 171], "with": "gfx100s-20260917-211657",
                                "basis": "the two originals' transactions agree entry for entry over these rows"},
            "pushes": pushes,
            "dynamicRange400": {"basis": "the trace; each bank held DR100 with D-Range Priority off before its push",
                                "accepted": {"bank": 2, "writeSequence": dr[0]["sequence"], "readbackUnsigned": 400},
                                "refused": [{"bank": push["bank"], "writeSequence": row["sequence"], "response": "0x201C",
                                             "readbackUnsigned": push["bankAfterUnsigned"]["0xD190"]}
                                            for push, row in zip(pushes[1:], dr[1:])],
                                "valuesThatDifferedBefore": {"0xD193": [20, 0, 0], "0xD194": [65526, 0, 0],
                                                             "0xD195": [7, 6, 6]},
                                "isoRecorded": False},
            "clientWithheld": [{"bank": note["bank"], "properties": note["properties"]} for note in withheld],
            "notEstablished": ["the ISO of each bank, which the client did not read",
                               "why C3 and C4 refused DR400", "USB mode", "AUTO UPDATE CUSTOM SETTING, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
