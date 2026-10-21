# GFX100S fw 2.13 owner report, 2026-09-29 22:20: sanitized evidence

This package is a deterministic, allowlisted derivative of a camera report a GFX100S owner exported from the maintainers' iOS client and labeled "C2 PROPERTY REPORT": TestFlight build 8, iPadOS 26.3, through ImageCaptureCore, generated at `2026-09-30T02:19:25Z`. Its trace reads all six banks. Its client records carry the D-Range Priority comparisons and pushes of earlier sessions, including one on 2026-09-19 that no report traces. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `7c178d6b6aa03bce81abf5b147349c3e90e31431bac1d5d23472136e6a7d7959`. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 167 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, its bank reads, an undated property sweep of bank 1, push records, guided tests with their menu comparisons, and the profile harvest, carried from earlier sessions with their own times. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 160 scalar payloads and 2 empty-name reads (C5 and C6), and omits 5 payload fields: DeviceInfo and the C1–C4 names. The serial hash, host device model, session identifiers, USB identifiers, and every bank and recipe name are omitted; the exporter searched every output for the 34 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Six banks | Rows 2–167 | The selector reads `1`; C1–C6 selected and read in full; the client then selects C1 again (166–167); nothing but the selector is written. |
| D-Range Priority in the trace | Row 9, and the same offset in each bank | C1 holds `0xD191` = `32768` (`0x8000`, Auto) with Dynamic Range `65535` (DR Auto). C2 holds `0` (Off) with DR `400`; C3–C6 hold `0` with DR `100`. |
| 2026-09-19 comparisons | The client's guided-test records | C1: the client showed D-Range Priority Auto, and the owner marked the row as differing, with the camera showing **OFF**. C2: the client showed Auto with DR400 overridden, and the row matched. |
| 2026-09-30 comparisons | The client's guided-test records | C1 again: client Auto, camera **OFF**. C2: client Off with DR400, matched. |
| `0xD191` refused | The client's push record from `2026-09-19T01:08:59Z` | A push to C1 partially applied: `0xD191` refused with `0x201C`. |

The comparisons and refusals are the client's records, carried forward from the session in which they were made; the owner's menu readings are as the client recorded them, not photographs. Together with the trace, they support the [custom-bank chapter's](../../docs/04-custom-slots.md#the-d-range-priority-interlock) GFX100S statements: on 2026-09-19 the client showed both C1 and C2 as Auto, the value it shows for `0x8000`, while the owner read C2 as AUTO and C1 as OFF on the camera, and a later write to `0xD191` on C1 was refused. The bytes behind the 2026-09-19 reading aren't traced; this trace's own C1 read is `0x8000`. Their evidence tag stays `[Owner report: GFX100S fw 2.13]`.

The package doesn't establish any bank's ISO, which the client doesn't read; whether the owner's reported ISO change on C1 was saved to the bank; the 2026-09-19 session's transactions; the USB mode; or AUTO UPDATE CUSTOM SETTING, lens, and image format. The owner's file label doesn't change what the client traced. The property sweep reads `0xD191` as `0` on bank 1, unlike this trace's C1 read; it isn't timestamped, so which session it comes from isn't established.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260929-222001/export.py \
  "ARCHIVE_DIR/C2 PROPERTY REPORT fuji-cookbook-camera-report-GFX100S-20260929-2219.json" --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
