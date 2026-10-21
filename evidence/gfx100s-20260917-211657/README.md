# GFX100S fw 2.13 owner report, 2026-09-17 21:16, RAF upload: sanitized evidence

This package is a deterministic, allowlisted derivative of a camera report a GFX100S owner exported from the maintainers' iOS client: TestFlight build 6, iPadOS 26.3, through ImageCaptureCore, generated at `2026-09-18T01:11:12Z` and updated at `01:16:57Z`. Its trace reads all six banks, uploads a RAF, and reads the conversion profile. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `459d958f5023140c9530d9e901f877067c94f28fabddb9cd9da6933a59e12278`, the hash [SOURCES](../../SOURCES.md#maintainer-hardware-records) has cited for the profile harvest and RAF upload. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record. The [21:51 package](../gfx100s-20260917-215104/README.md) is a later export from the same session: its first 171 rows are this trace, entry for entry.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 171 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, its bank reads, the property sweep, push records carried from 2026-09-15, the guided test with a six-bank menu comparison, the profile harvest, and a note. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 158 scalar payloads and 4 empty-name reads (C3–C6), and omits 8 payload fields: DeviceInfo, the C1 and C2 names, both handle lists, the object info, which names the file, the RAF itself, and the profile. The handle counts and the RAF's size are kept as numbers in `findings.json`, and the profile's first 64 bytes, which hold only its cell count, IOPCode, and padding, from the client's harvest record. The serial hash, host device model, session identifier, USB identifiers, and every bank name are omitted; the exporter searched every output for the 11 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Six banks | Rows 2–164 | The selector reads `6`; C1–C6 selected and read in full. |
| Profile before upload | Row 166 | `0xD185` answers `0x2002`. |
| Handles before | Row 167 | `GetObjectHandles` returns zero handles. |
| Upload | Rows 168–169 | `SendObjectInfo` and `SendObject` both `0x2001`; 208,071,296 bytes (198.43 MiB) in 5,392 ms, about 36.80 MiB/s (38.59 MB/s). |
| Handles after | Row 170 | Zero handles; the uploaded RAF isn't enumerated. |
| Profile after upload | Row 171 | 621 bytes. |
| Profile layout | The client's harvest record | 28 parameters, IOPCode `FF149502`, table at `0x1FD`. Of the candidate table offsets, `0x1FD` scores 5 and is accepted; `0x201` scores 3 and `0x1F9` scores 2. The client recorded that the upload created no object. |

These support the [conversion-profile chapter's](../../docs/06-conversion-profile.md) GFX100S rows, the [RAW-conversion chapter's](../../docs/05-raw-conversion.md) handle observation, and the [transport chapter's](../../docs/01-transport.md) upload timing. Their evidence tag stays `[Owner report: GFX100S fw 2.13]`.

The trace doesn't establish the RAF's contents or as-shot settings beyond the profile header, the USB mode, or AUTO UPDATE CUSTOM SETTING, ISO, lens, and image format.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260917-211657/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-GFX100S-20260917-2111.json --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
