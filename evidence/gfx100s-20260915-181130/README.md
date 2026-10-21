# GFX100S fw 1.32 owner report, 2026-09-15 18:11: sanitized evidence

This package is a deterministic, allowlisted derivative of the first camera report a GFX100S owner exported from the maintainers' iOS client: TestFlight build 2, iPadOS 26.3, through ImageCaptureCore. The report was generated at `2026-09-15T22:10:39Z`, before the owner updated the camera from firmware 1.32 to 2.13, and build 2 didn't recognize the body. The owner agreed to its publication. The [September records note](../gfx100s-september-records.md) connects this package to the others and to the record's claims.

The original's SHA-256 is `87f8055ed3a98368bec8fdb43e258a44fc6f6afb80addf63cf31c979d9cd508e`. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../gfx100s-september-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 114 traced transactions in order, none dropped by the client. |
| [`client-records.json`](client-records.json) | The client's own records, allowlisted: DeviceInfo, the property sweep, and the guided test's steps. |
| [`findings.json`](findings.json) | Mechanical observations over the trace, and the reviewed findings below. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | Run-specific review over the shared [owner-report exporter](../owner_report_package.py); rejects any original with a different hash. |

The ledger retains 51 scalar payloads and the two empty-name reads `010000`, and omits 3 payload fields: DeviceInfo and the two `0xD183` descriptors, whose parsed form the client's property sweep keeps. The serial hash, the host device model, the guided test's session identifier, the USB identifiers, and every bank name are omitted; the exporter searched every output for the 3 private strings the original holds before writing.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| Firmware and identity | DeviceInfo, row 1 | Firmware 1.32, 601 bytes, 168 properties; `GetDeviceInfo` took 5 ms. The client's identification is `unknown`. |
| Selector without a select | Row 2 | `0xD18C` reads `7`, with no selector write anywhere in the trace. |
| Image Size there | Row 10 | `0xD18E` reads `16`. |
| Bank block | Two read passes, rows 2–110 | All 53 bank-block reads answer `0x2001`; all 52 bank-block descriptor requests, two per property, answer `0x200A`. |
| `0xD185` and `0xD183` | Rows 6–9 and 111–114 | `0xD185`: value `0x2002`, descriptor `0x200A`. `0xD183`: value `0x200A`, descriptor answered; the client's sweep parses it as UINT16, read/write, enumeration `0`, `1`, default and current `65535`. |

These support the [transport chapter's](../../docs/01-transport.md) descriptor table and firmware row, and the [encoding chapter's](../../docs/03-encodings.md) Image Size `16` row. Their evidence tag stays `[Owner report: GFX100S fw 1.32]`.

The trace doesn't establish the USB mode; why the selector read 7, a bank the fw 2.13 traces refuse to select; whether the block addressed a bank the camera shoots with; or AUTO UPDATE CUSTOM SETTING, ISO, lens, and image format.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/gfx100s-20260915-181130/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-GFX100S-20260915-1810.json --check
```

To regenerate the four artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporters and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
