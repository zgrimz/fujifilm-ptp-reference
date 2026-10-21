#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run-specific reviewed projection; private originals are read, never copied."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_report_package import bank_pass, bank_write, package_main, scalar, transaction  # noqa: E402

SPEC = {"evidenceId": "gfx100s-20260915-195437",
        "sourceSha256": "f79dd70084a0ad1a040c3d4c5e1101ae7f8e934dc7b46db9949937f2eb2a03a9",
        "sourceRevision": "a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9",
        "sourcePath": "hardware-runs/app-reports-gfx100s/2026-09-15/fuji-cookbook-camera-report-GFX100S-20260915-1953.json",
        "transactionCount": 237}


def review(original, rows, records, observed):
    banks = bank_pass(rows, 2)
    if scalar(transaction(rows, 164, "0x1016", "0xD18C", "0x200A"), "out") != 7:
        raise ValueError("expected bank 7 refused")
    trial_bank = banks[1]["bankSettingsUnsigned"]
    if (trial_bank["0xD193"], trial_bank["0xD194"], trial_bank["0xD195"]) != (20, 65526, 5):
        raise ValueError("expected C2 to hold the trial recipe after the power cycle")
    tests = [test for test in records["guidedTests"] if "writePass" in test]
    if len(tests) != 1 or len(tests[0]["writePass"]["trials"]) != 1:
        raise ValueError("expected one write-pass trial")
    trial = tests[0]["writePass"]["trials"][0]
    comparison = trial["menuComparison"]
    if (trial["bank"], trial["outcome"], trial["persistence"]["persisted"], trial["persistence"]["nameHolds"],
            trial["photoMatchesRecipe"], comparison["verdict"], len(comparison["rows"])) != \
            (2, "applied", True, True, "yes", "matches", 12) or any(row["differs"] for row in comparison["rows"]):
        raise ValueError("expected the trial applied, persisted and menu-confirmed")
    toning = [row["clientShowed"] for row in comparison["rows"] if row["field"] == "Monochromatic Color"]
    push, restore = records["pushes"]
    rejected = [(field["property"], field.get("response")) for field in push["fields"] if field["outcome"] != "written"]
    pushed_grain = [field["writtenUnsigned"] for field in push["fields"] if field["property"] == "0xD195"]
    if (push["kind"], push["bank"], push["recordedUtc"], len(push["fields"]), rejected, push["nameWritten"],
            push["bankBeforeUnsigned"]["0xD195"], pushed_grain) != \
            ("push", 2, trial["pushedUtc"], 22, [("0xD191", "0x201C"), ("0xD1A5", "0x201C")], True, 6, [5]):
        raise ValueError("expected the trial push record")
    if (restore["kind"], restore["bank"]) != ("restore", 2):
        raise ValueError("expected the restore record")
    written = bank_write(rows, 165)
    responses = [(row["property"], row["response"]) for row in written["writes"]]
    if written["bank"] != 2 or written["nameWrite"]["response"] != "0x2001" or len(responses) != 21 or \
            responses[-1] != ("0xD1A5", "0x201C") or any(response != "0x2001" for _, response in responses[:-1]):
        raise ValueError("expected the restore: a name write, 20 accepted settings and D1A5 refused")
    if written["writes"][-1]["writtenUnsigned"] != written["liveD1A5BeforeUnsigned"] or \
            written["acceptedWritesReadBackDifferently"] != [{"property": "0xD195", "writtenUnsigned": 1,
                                                              "readbackUnsigned": 7}]:
        raise ValueError("expected D1A5 refused at its current value and grain Off read back as 7")
    return {"bankPass": banks,
            "bankSevenSelect": {"writeSequence": 164, "valueUnsigned": 7, "response": "0x200A"},
            "trialOnC2AfterPowerCycle": {
                "readSequences": banks[1]["readSequences"], "toningUnsigned": {"0xD193": 20, "0xD194": 65526},
                "toningSigned": {"0xD193": 20, "0xD194": -10}, "grainUnsigned": 5,
                "clientRecord": {"pushedUtc": trial["pushedUtc"], "outcome": "applied",
                                 "persistenceCheckedUtc": trial["persistence"]["checkedUtc"], "persisted": True,
                                 "nameHolds": True, "photoMatchesRecipe": "yes",
                                 "menuComparison": {"checkedUtc": comparison["checkedUtc"], "rows": 12, "differences": 0,
                                                    "monochromaticColorClientShowed": toning[0]}},
                "trialPushRecord": {"recordedUtc": push["recordedUtc"], "fields": 22, "written": 20,
                                    "refused": [{"property": "0xD191", "response": "0x201C"},
                                                {"property": "0xD1A5", "response": "0x201C"}],
                                    "nameWritten": True, "grainBeforeUnsigned": 6, "grainWrittenUnsigned": 5},
                "pushTransactions": "not in this trace; the client traced only its last connection"},
            "restoreOfC2": written,
            "grainRollback": {"savedUnsigned": 6, "trialUnsigned": 5, "restoreWroteUnsigned": 1, "readbackUnsigned": 7,
                              "readSequence": written["afterReadSequences"][0] + 7},
            "notEstablished": ["the trial push's own transactions", "the power cycle itself, beyond the client's record",
                               "USB mode", "AUTO UPDATE CUSTOM SETTING, ISO, lens and image format"]}


if __name__ == "__main__":
    raise SystemExit(package_main(SPEC, review, __file__))
