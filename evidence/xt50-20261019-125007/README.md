# X-T50 October 19 client restore with an empty name: sanitized evidence

This package contains a deterministic, allowlisted derivative of a camera report that the maintainers' iOS client exported from an X-T50 on firmware 1.32, through ImageCaptureCore on iOS 27.0.1. Its trace covers the client's last connection of a scripted camera test, which restored bank C7 to an empty name and its original 23 settings: one write of the one-byte empty PTP string to `0xD18D`, 20 bank-setting writes after it, and the reads that close the restore. The [evidence index](../README.md) explains the package layout; this page covers what differs from the bankprobe packages.

The original's SHA-256 is `905ec32db38047acff668b141c5fde1cf055f861438b43d330a1ec5d89b7c800`; it stays in the maintainers' private archive at revision `2a3d1221d130e8d7cddf02f9f746dfe8adfa147b`, at the path the [manifest](manifest.json) records. The [source inventory](../xt50-20261019-client-sources.json) also hashes the problem report and test results exported from the same run, which aren't used here.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 339 traced transactions of the connection in order, none dropped by the client. |
| [`findings.json`](findings.json) | The reviewed restore of C7 with sequence numbers, and two of the client's own records about C7, labeled as such. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, host and conditions, omissions, and hashes of the three exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [client-report exporter](../client_report_package.py); rejects any original with a different hash. |

A client trace differs from a bankprobe log in four ways. Each row is a command as the client handed it to ImageCaptureCore, with the data phase it supplied or received, the response ImageCaptureCore returned, and a host-measured `durationMs`; the bytes on the USB wire aren't observed. `sequence` is the client's own count within the connection, and ImageCaptureCore numbers the PTP transactions itself, so no transaction ID is kept. The client keeps outgoing bytes only up to 16 bytes and cuts incoming bytes off at 64, so a long name write carries a length and no bytes in the original. Parameters are kept only for property reads, writes, and descriptor requests; every other operation keeps its parameter count.

The ledger retains 312 scalar payloads on the selector, bank, and live `0xD1A5` allowlist and the one `0xD18D` payload that holds no name, `emptyNameOutHex` `00`. It omits 25 payload fields with their lengths: DeviceInfo, the conversion-profile, trigger, and object payloads of a develop in the same connection, and every name. All 339 transactions record `0x2001`. The [manifest](manifest.json) keeps the client's keyed camera identifier (`hmac-sha256`), which a guessed serial can't be checked against; the connection identifier, USB identifiers, and phone model are omitted, as are the client's push, develop, and camera-test records apart from the fields `findings.json` cites.

## The restore and its readbacks

| Step | Source evidence | Result |
|---|---|---|
| Select C7 | Write 269, read 270 | `0700`, both `0x2001`. No other selector write follows. |
| Bank settings | Reads 271–293 | The 23 bank settings, all `0x2001`. |
| Name before | Read 294 | A non-empty name, response `0x2001`; contents omitted. |
| Write the empty name | Write 295 | Payload `00`, one byte handed to ImageCaptureCore; response `0x2001`. |
| Write 20 bank settings | Writes 296–315 | `0xD18E`–`0xD1A4` except `0xD193`, `0xD194`, and `0xD19C`; all `0x2001`. |
| Read the settings | Reads 316–338 | Every written setting reads back the value written. |
| Read the name | Read 339 | Response `0x2001`; byte-equal to read 294, a non-empty name, not either empty form. |

No `0xD18D` read falls between write 295 and read 339, so the trace doesn't show the name in between. The client's own records in the same report, whose transactions precede this trace, say that C7's name read empty before the test pushed a non-empty name to it, that the pushed name read back as written, and that this restore wrote the empty name and recorded it as mismatched.

This supports one statement: through ImageCaptureCore on iOS 27.0.1, the X-T50 answered `0x2001` to the one-byte empty name followed by 20 bank-setting writes, and the name read afterward was the one the bank held before. The [October 19 bankprobe package](../xt50-20261019-102738/README.md), on the same body and day, wrote the same byte over direct USB with no bank setting after it and read the unnamed form. The two runs differ in transport and in what followed the name, so neither run isolates the cause; [open questions](../../docs/open-questions.md#bank-protocol) lists the comparison that would. The trace starts at `2026-10-19T16:50:07Z`. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261019-125007/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-X-T50-20261019-1250.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and all three exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction/privacy checks do not independently prove a hardware observation occurred. The derivative is not a lossless backup.
