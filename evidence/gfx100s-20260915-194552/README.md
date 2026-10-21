# GFX100S fw 2.13 owner report, 2026-09-15 19:45: sanitized evidence

This package is a deterministic, allowlisted derivative of a camera report a GFX100S owner exported from the maintainers' iOS client: TestFlight build 3, iPadOS 26.3, through ImageCaptureCore, generated at `2026-09-15T23:45:11Z`, after the owner updated the camera to firmware 2.13. Its trace reads all six banks, tries to select a seventh, sweeps C1's properties, and probes the grain property. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `144c2951b93280c5c1c29761e7f51dac166da6b0cabaf6ba91418cd2a9ec9c94`. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 244 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, its bank reads, the property sweep, the guided test with its six-bank menu comparison and grain probe, and its notes. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 206 scalar payloads and 5 empty-name reads (C2–C6, rows 31–139), and omits 4 payload fields: DeviceInfo, a `0xD183` descriptor, and C1's name, read in the bank pass and again in the property sweep. The serial hash, host device model, session identifier, USB identifiers, and every bank name are omitted; the exporter searched every output for the 7 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Firmware | DeviceInfo, row 1 | 2.13, against 1.32 in the [18:11 report](../gfx100s-20260915-181130/README.md) the same evening. |
| Six banks | Rows 2–163 | C1–C6 each selected, read back, and read in full; every bank holds Image Size `14`, Image Quality `2`, and `0xD1A5` `14`. |
| Bank 7 | Row 164 | Selecting 7 answers `0x200A`; row 165 selects C1. |
| C1's values | Rows 5–28 | DR Auto `65535`, grain `3`, White Balance `32770` (`0x8002`, Fluorescent 2) with shifts `65534`/`65534` (−2/−2), Sharpness `65516` (−20), High ISO NR `32768` (`0x8000`). |
| Menu comparison | The client's guided-test record | All six banks, 12 rows each, matched the owner's reading of the camera's menu. |
| Grain probe on C1 | Rows 223–244 | Starting from `3`: `0` refused (`0x201C`); `2` accepted, reads `2`; `1` accepted, reads `6`; `3` accepted; `6` refused; `4` accepted; `7` refused; `5` accepted, reads `5`; `1` accepted, reads `7`; `8` refused. |

These support the [camera chapter's GFX100S section](../../docs/07-cameras.md#gfx100s), [custom banks](../../docs/04-custom-slots.md#how-many-banks), and the [encoding chapter's](../../docs/03-encodings.md) grain, white balance, sharpness, and noise reduction rows. Their evidence tag stays `[Owner report: GFX100S fw 2.13]`; the menu comparison is the owner's reading as the client recorded it, not a photograph.

The trace doesn't establish the USB mode, or AUTO UPDATE CUSTOM SETTING, ISO, lens, and image format. The grain probe leaves C1 at `7`; nothing in this trace restores it.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260915-194552/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-GFX100S-20260915-1945.json --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
