# X-T50 October 16 reset-check run: sanitized evidence

This package contains a deterministic, allowlisted derivative of the recovered `bankprobe-20261016-095611.json` run on X-T50 firmware 1.32, bank C7. It exposes two changed-value RESET controls and a separate enter/back-out observation. It is a historical test, not a new hardware run. The [October records note](../xt50-october-records.md) retains the earlier reverting reset result; this package doesn't resolve that conflict or the unknown AUTO UPDATE setting. The [evidence index](../README.md) explains the files.

The original's SHA-256 is `fafde86c62e91efc75cea8f91d66f29205a899454a5c5618c21ae0cceb847ddb`; it and its paired transcript stay in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, at the paths the [manifest](manifest.json) and [findings](findings.json) record. The transcript's procedure references are reviewed annotations; the exporter doesn't re-read it.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 221 original entries in order: 213 operation rows and eight host reconnect-event rows. |
| [`findings.json`](findings.json) | Three numeric stages, normalized operator observations, and separate procedure instructions, name equality comparisons, and the limited cleanup comparison. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, counts, conditions, omissions, and hashes of both exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [package exporter](../bankprobe_package.py); rejects any original with a different hash. |

The ledger retains 189 scalar payload fields and omits 14 other payload fields. It records 204 OK responses, no recorded refusals, and nine operations with no recorded response. Unknown outcomes retain `response: null`, `outcome: "outcome_unknown"`, and transport-error presence without the private error text. A host reconnect is not independent power telemetry, and a missing response is not acceptance or refusal. Responses are from a host-generated report, without independently correlated bus provenance.

The original has no top-level before/after snapshot pair; no snapshot artifact is invented.

## Reset evidence and its limits

Initial Film Simulation is `12` at index 15. All listed writes and reads return `0x2001`. The changed-value stages are:

| Stage | Before → intended → immediate read → later read | Write / immediate read / later read indices | Menu action and reported result |
|---|---|---|---|
| R: bare write | `12→2→2→2` | 62 / 63 / 78 | Operator reports a dot, RESET available and performed; Velvia remains. |
| N: write plus name | `2→12→12→12` | 98 / 99 / 115 | Name written at 100; operator reports a dot, RESET available and performed; ACROS remains. |
| V: bare write then item entry | `12→2→2→2` | 135 / 136 / 151 | Operator reports entering/leaving Film Simulation without changing it clears the dot and makes RESET and SAVE unavailable. |

The first two procedures explicitly prohibit EDIT/CHECK or opening an item (paired transcript lines 43/54). The operator responses report the reset action and resulting simulation, but do not independently confirm every requested menu-path restriction. Findings distinguish the instruction from the reported action. The third procedure explicitly requests entering and backing out of the item (line 64). Its operator response says RESET became unavailable, so it is not a third executed RESET control.

The name write in stage N returns `0x2001`, and a transient private-byte comparison establishes that it sends the name initially read at index 10. Its contents remain omitted. The numeric trials establish that both the bare-write and write-plus-name RESET cases retained their changed values under this run's conditions. They do not show that a name write is required or explain why the earlier `002045` run reverted.

## Cleanup and conditions

Cleanup writes/readbacks at indices 175–216 cover 21 of the 23 bank settings, all with `0x2001` and values matching initial reads. Live `0xD1A5` at 217/218 also matches its initial sample. `0xD19C` Kelvin and `0xD19F` Color are neither written nor freshly read during cleanup. Name write/read 173/174 matches the initial name; final name write 219 sends those same bytes but has no later readback. CloseSession 220 has a transport error and no response. A subsequent manual-save/Q-menu check is instructed without a recorded explicit result. This is limited cleanup evidence, not proof of exact whole-bank restoration or later persistence.

The source records local start time `2026-10-16T09:56:11`, without timezone/offset. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format remain unconfirmed. There are no independent menu photographs, power measurements, or rendered-pixel evidence in this package. Source recovery does not convert requested setup into observed setup.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261016-095611/export.py \
  ARCHIVE_DIR/bankprobe-20261016-095611.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and both exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction checks do not independently prove hardware observations occurred, and this derivative is not a recovery backup.
