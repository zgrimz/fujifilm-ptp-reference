# GFX100S fw 2.13 owner report, 2026-09-17 21:51, DR400 pushes: sanitized evidence

This package is a deterministic, allowlisted derivative of a later export of the same session as the [21:16 package](../gfx100s-20260917-211657/README.md): TestFlight build 6, iPadOS 26.3, through ImageCaptureCore, generated at `2026-09-18T01:11:12Z` and updated at `01:51:04Z`. Its first 171 rows are the 21:16 trace, entry for entry; after them the client pushed a recipe with DR400 to C2, C3, and C4. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `2be55bb14c39ac592a94ebf2f8f36eb9fcc6dd2e5e99f138b6988fbca0823be8`. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 384 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, its bank reads, the property sweep, five push records, the guided test, the profile harvest, and the client's notes on withholding two properties. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 365 scalar payloads and 6 empty-name reads, and omits 12 payload fields: the 8 the 21:16 package omits, a further name read, and the three pushes' name writes. The serial hash, host device model, session identifier, USB identifiers, and every bank and recipe name are omitted; the exporter searched every output for the 20 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Rows shared with the 21:16 report | 1–171 | The six-bank read and the RAF upload, as the [21:16 package](../gfx100s-20260917-211657/README.md) describes. |
| Before each push | 174–197, 245–268, 316–339 | C2, C3, and C4 all hold DR100 (`100`) with D-Range Priority Off (`0`). They differ in Monochromatic Color (C2 `20`/`65526`, the others `0`/`0`) and grain (C2 `7`, the others `6`). |
| Push to C2 | 172–242 | Name written, 103 ms (199); 19 settings, all `0x2001`, DR400 among them (202); every value reads back as written, DR `400` (221). |
| Push to C3 | 243–313 | Name written, 329 ms (270); DR400 refused with `0x201C` (273), DR reads back `100` (292); the other 18 settings accepted. Grain written `1` reads back `6`. |
| Push to C4 | 314–384 | Name written, 103 ms (341); DR400 refused with `0x201C` (344), DR reads back `100` (363); the other 18 settings accepted. |
| `0xD191` and `0xD1A5` | The client's notes | The client withheld both from all three pushes, because this body had refused them; neither appears in the trace's writes. |

These support the [custom-bank chapter's](../../docs/04-custom-slots.md#iso-gating) GFX100S DR400 statement. Its evidence tag stays `[Owner report: GFX100S fw 2.13]`.

The trace doesn't establish each bank's ISO, which the client doesn't read, so it doesn't explain why C3 and C4 refused DR400. It doesn't establish the USB mode, or AUTO UPDATE CUSTOM SETTING, lens, and image format.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260917-215104/export.py \
  "ARCHIVE_DIR/fuji-cookbook-camera-report-GFX100S-20260917-2111 2.json" --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
