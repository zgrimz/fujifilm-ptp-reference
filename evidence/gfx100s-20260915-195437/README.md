# GFX100S fw 2.13 owner report, 2026-09-15 19:54, write pass: sanitized evidence

This package is a deterministic, allowlisted derivative of the camera report a GFX100S owner exported from the maintainers' iOS client at the end of its write pass: TestFlight build 3, iPadOS 26.3, through ImageCaptureCore, generated at `2026-09-15T23:53:56Z`. The client pushed a test recipe to C2, the owner power-cycled the camera and checked the bank and a photo, and the client restored C2. Its trace covers the last connection: a read of all six banks after the power cycle, and the restore. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `f79dd70084a0ad1a040c3d4c5e1101ae7f8e934dc7b46db9949937f2eb2a03a9`, the hash [SOURCES](../../SOURCES.md#maintainer-hardware-records) has cited for the write pass. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 237 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, its bank reads (taken after the restore), the property sweep, the trial and restore push records, and the guided tests with the write pass. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 228 scalar payloads and 4 empty-name reads (C3–C6), and omits 5 payload fields: DeviceInfo, three reads of the C1 and C2 names, and the restore's name write. The serial hash, host device model, session identifiers, USB identifiers, the test recipe's name, and every bank name are omitted; the exporter searched every output for the 12 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Six banks, bank 7 refused | Rows 2–164 | C1–C6 selected and read in full; selecting 7 answers `0x200A`. |
| The trial on C2 after the power cycle | Rows 29–55 | Monochromatic Color WC `20` (`0x0014`, +2) and MG `65526` (`0xFFF6`, −1); grain `5` (Strong, Large). |
| The trial as the client recorded it | Write-pass record | Pushed at `23:49:13Z`; after the power cycle, at `23:50:12Z`, the settings persisted and the name held; the owner judged the photo to match the recipe; at `23:53:18Z` all 12 menu rows matched, Monochromatic Color shown as WC +2, MG −1. |
| The trial push | The client's push record | 22 fields: 20 written, `0xD191` and `0xD1A5` refused with `0x201C`; the name written. C2's grain before the push was `6`, and the push wrote `5`. The push's own transactions aren't in this trace. |
| The restore of C2 | Rows 165–237 | Select and read C2 (165–190); read the name (191); write it, 325 ms (192); 20 settings accepted (193–212); `0xD1A5` written with its current value `14` and refused, `0x201C` (213); read back (214–237). |
| Grain after the restore | Row 221 | The restore wrote `1` (Off) and reads back `7`: Off restored, at the large size the trial left rather than the small size saved. Every other accepted write reads back as written. |

These support the [camera chapter's](../../docs/07-cameras.md#gfx100s) write-pass and `0xD1A5` statements, the [platform notes'](../../docs/09-platform-notes.md) iOS 26 GFX100S row, and the [encoding chapter's](../../docs/03-encodings.md) Monochromatic Color and grain-rollback statements. Their evidence tag stays `[Owner report: GFX100S fw 2.13]`; the persistence check, photo judgment, and menu rows are the owner's, as the client recorded them.

The trace doesn't establish the trial push's transactions, the power cycle beyond the client's record, the USB mode, or AUTO UPDATE CUSTOM SETTING, ISO, lens, and image format. The client's bank-read record was taken after the restore, so it shows C2 restored, not the trial.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260915-195437/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-GFX100S-20260915-1953.json --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
