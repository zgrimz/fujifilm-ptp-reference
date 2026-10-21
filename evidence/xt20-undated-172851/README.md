# X-T20 fw 2.01 owner log: sanitized evidence

This package is a deterministic, allowlisted derivative of the app-log excerpt an X-T20 owner exported from the maintainers' iOS client and sent on 2026-09-14. The log covers four connections between 17:28:51 and 17:32:45 local time, with no date, and ends with the client's property report for C1. The owner agreed to its publication. The [evidence index](../README.md) explains how owner-report packages differ from the maintainers' own.

The original's SHA-256 is `061306bc4670986ed312fa391e991f1cb819ca7b18ca6f997221128935486f62`, the hash [SOURCES](../../SOURCES.md#maintainer-hardware-records) has cited since the log was received. It stays in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`, at the path the [manifest](manifest.json) and the [source inventory](../xt20-sources.json) record.

## Files and coverage

| File | Contents |
|---|---|
| [`log.jsonl`](log.jsonl) | All 150 lines in order, one typed row per line: 59 log lines and 91 property-report lines. |
| [`findings.json`](findings.json) | The four connections, the DeviceInfo they share, and the property report's 28 entries. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, unknown conditions, omissions, and exporter hashes. |
| [`export.py`](export.py) | The exporter; rejects any original with a different hash. |

Every line must match one of 30 reviewed line forms, or the exporter stops. A row keeps the line number, the log's time of day, an event name, and the matched fields: model, firmware, PTP operation and property codes, counts, and response codes. The exporter also refuses any output that holds a hexadecimal run longer than a PTP code.

The original holds no serial number and no serial hash. The client's log prints a summary of `GetDeviceInfo`, not the dataset, and the property report reads no identity property. The package omits the USB vendor and product identifiers, the client's property labels and prose, and the log's category tag. The client's labels aren't the record's: the report labels `0xD1A3` "Long-Exposure NR", which [the property table](../../docs/02-properties.md#the-23-bank-settings) identifies as Lens Modulation Optimizer.

## What it establishes

| Observation | Source rows | Result |
|---|---|---|
| DeviceInfo | Lines 10–13, repeated at 26–29, 43–46, and 55–58 | 595 bytes, PTP 100, vendor extension `0x00000006` `fujifilm.co.jp: 1.0; `, firmware 2.01. 27 operations and 168 properties, identical in all four connections. No property from `0xD162` to `0xD1FF`, so neither the bank block nor `0xD183`/`0xD185` is advertised. |
| An error after each DeviceInfo | Lines 14, 30, 47, 59 | `0x200A`, logged 25–40 ms after the DeviceInfo line. The log doesn't say which read it answered. |
| Bank block | Lines 66–143 | All 26 properties `0xD18C`–`0xD1A5`: value `0x200A`, descriptor `0x200A`. |
| `0xD185` | Lines 144–146 | Value `0x2002`, descriptor `0x200A`. |
| `0xD183` | Lines 147–150 | Value `0x200A`; the descriptor answers: UINT16, read/write, enumeration `0`, `1`, default `65535`, current `65535`. |
| Time to DeviceInfo | Session-open and DeviceInfo lines of each connection | 1,556 ms in the first connection, 9, 19, and 9 ms in the next three. These are differences between log-line times, not PTP transaction durations. |

These support the [camera chapter's X-T20 section](../../docs/07-cameras.md#x-t20) and the [transport chapter's](../../docs/01-transport.md) X-T20 rows. Their evidence tag stays `[Owner report: X-T20 fw 2.01]`; this package makes the report inspectable, and adds no new hardware observation.

The log doesn't establish the date, time zone, client build, or host system version; the USB mode or any `0xD16E` reading; whether a selector write succeeded, since the report's C1 heading is the client's label; which connection the property report came from; any RAF upload or conversion; or AUTO UPDATE CUSTOM SETTING, ISO, lens, and image format. [Open questions](../../docs/open-questions.md) lists the X-T20 tests still wanted.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt20-undated-172851/export.py ARCHIVE_DIR/xt20.txt --check
```

To regenerate the three artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporter and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivative isn't a lossless backup.
