# X-T50 October 16 name-timing run: sanitized evidence

This package contains a deterministic, allowlisted derivative of the recovered `bankprobe-20261016-094028.json` run on X-T50 firmware 1.32, bank C7. It makes four name-timing observations and their limits inspectable. It is a historical test, not a new hardware run. For the wider reset/persistence disagreement, see the [October records note](../xt50-october-records.md); for how to read the files, see the [evidence index](../README.md).

The original's SHA-256 is `96bf39bf6f5b696f902d2ab1e0e60ebb05bff9132fc4562863a04993419a63f8`; it and its paired transcript stay in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, at the paths the [manifest](manifest.json) and [findings](findings.json) record. The transcript's procedure references are reviewed annotations; the exporter doesn't re-read it.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 134 original entries in order: 124 operation rows and ten host reconnect-event rows. |
| [`findings.json`](findings.json) | Four numeric trials, name equality comparisons, normalized operator observations with source pointers, procedure references, and the limited cleanup comparison. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, counts, conditions, omissions, and hashes of both exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [package exporter](../bankprobe_package.py); rejects any original with a different hash. |

The ledger retains 93 scalar payload fields and omits 16 other payload fields. It records 113 OK responses, no recorded refusals, and 11 operations with no recorded response. Those 11 retain `response: null` and `outcome: "outcome_unknown"`; an omitted transport-error message is represented only by its presence. Neither missing completion nor reconnect events establish camera acceptance or a power cycle. Responses are from a host-generated report, without independently correlated bus provenance.

The source has no top-level before/after snapshot pair, so no snapshot artifact is invented.

## Four scoped observations

Initial Film Simulation is `12` at index 15. Each following write returns `0x2001`, and its immediate read returns `0x2001` with the intended value. Each name write also returns `0x2001`. Comparing private bytes during export establishes that all four name writes equal the name initially read at index 10; no name bytes or name hashes are published.

| Reported condition | Intended Film Simulation | Write / read / name indices | Readback | Operator observation |
|---|---:|---|---:|---|
| Immediate name, same PTP session | 2 | 35 / 36 / 37 | 2 | Dot present; entering Film Simulation and backing out clears it, leaving SAVE unavailable. |
| Name after a reported ten-second wait | 12 | 45 / 46 / 47 | 12 | Dot present; operator explicitly reports not entering the item, then saving. |
| Name after a new PTP session | 2 | 55 / 56 / 62 | 2 | Dot present, then saved; item-entry behavior is not explicitly reported. |
| Name after an instructed cable reconnect | 12 | 70 / 71 / 76 | 12 | Dot present, then saved; item-entry behavior is not explicitly reported. |

The delay is reported by the transcript, not independently measured: operation rows have no timestamps. The third stage has accepted CloseSession/OpenSession at indices 57/59; the reused session parameter does not establish a unique connection identifier. The fourth has a five-second unplug/replug instruction and operator continuation, not independent cable telemetry. The failed attempts before successful retry writes remain visible in the full ledger.

These observations support “name writes did not clear the dot under these conditions.” They do not isolate a general commit mechanism or establish four controls in which no item was entered. The first observation explicitly includes entering an item, only the second explicitly excludes it, and the last two leave that behavior unknown. Numeric immediate readbacks and later operator menu observations are distinct evidence; this run does not read Film Simulation after each menu inspection before moving to the next write.

## Cleanup and conditions

Cleanup writes/readbacks at indices 88–129 cover 21 of the 23 bank settings, all with `0x2001` and values matching their initial reads. Live `0xD1A5` at 130/131 also matches its initial sample. `0xD19C` Kelvin and `0xD19F` Color are neither written nor freshly read in that cleanup sequence. The name write/read at 86/87 matches the initial name; the final name write at 132 also sends the initial bytes but has no later readback. CloseSession at 133 has a transport error and no recorded response. A later manual-save/Q-menu check is instructed, without a recorded explicit result. These facts do not establish exact whole-bank restoration or later persistence.

The source's local start time is `2026-10-16T09:40:28`, with no offset/timezone. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed. Procedure requests are not observations of actual configuration. There are no independent menu photographs, power measurements, or rendered-pixel evidence in this package.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261016-094028/export.py \
  ARCHIVE_DIR/bankprobe-20261016-094028.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the original hash, rejects an original inside the checkout, and never modifies or copies the original. The manifest hashes both data files and both exporter modules. This README is separately reviewed interpretation. Public regression tests require no private original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction and privacy checks do not independently prove a hardware observation occurred.
