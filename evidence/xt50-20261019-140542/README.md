# X-T50 October 19 client undo with the three-byte empty name: sanitized evidence

This package contains a deterministic, allowlisted derivative of a camera report that the maintainers' iOS client exported from an X-T50 on firmware 1.32, through ImageCaptureCore on iOS 27.0.1. Its trace covers one connection, in which the client pushed a recipe to bank C7, which had no name, and then undid the push. The undo wrote the empty name as `01 00 00`, the bytes an unnamed bank answers, and 19 bank settings after it. The [client restore package](../xt50-20261019-125007/README.md) describes how a client trace differs from a bankprobe log; this one follows the same format.

The original's SHA-256 is `23a8d14188add4d699bcd614d492a2775078a1637fb2f88d94339d864e316430`; it stays in the maintainers' private archive at revision `50dabec6c251f39d30a6c962daafd4c71c7bde7d`, at the path the [manifest](manifest.json) records. The [source inventory](../xt50-20261019-140542-sources.json) also hashes the problem report exported from the same run, which isn't used here.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 325 traced transactions of the connection in order, none dropped by the client. |
| [`findings.json`](findings.json) | The push and the undo of C7 with sequence numbers, and the client's records of both, labeled as such. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, host and conditions, omissions, and hashes of the three exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [client-report exporter](../client_report_package.py); rejects any original with a different hash. |

The ledger retains 311 scalar payloads on the selector, bank, and live `0xD1A5` allowlist and the four `0xD18D` payloads that hold no name. It omits ten payload fields with their lengths: DeviceInfo and every name. All 325 transactions record `0x2001`.

## The push and the undo

| Step | Source evidence | Result |
|---|---|---|
| Read C7's name at connect | Read 161, after selecting C7 | `010000`, no name. |
| Push: select C7, read the bank | 186, 187; reads 188–210 | C7 read back; 23 settings, all `0x2001`. |
| Push: name before, name write | Read 211, write 212 | `010000`; then a non-empty name, `0x2001`. |
| Push: settings, name after | Writes 213–231, reads 232–254, read 255 | 19 settings written and read back equal; a non-empty name. |
| Undo: select C7, read the bank | 256, 257; reads 258–280 | C7 read back; 23 settings, all `0x2001`. |
| Undo: name before | Read 281 | Byte-equal to read 255. |
| Undo: write the empty name | Write 282 | Payload `010000`, three bytes handed to ImageCaptureCore; response `0x2001`. |
| Undo: write 19 bank settings | Writes 283–301 | All `0x2001`. |
| Undo: read the settings | Reads 302–324 | Every written setting reads back the value written. |
| Undo: read the name | Read 325 | `010000`. |

No `0xD18D` read falls between write 282 and read 325. The client's own records in the same report say the push found C7's name empty and verified the name it wrote, and that the undo wrote the empty name and verified it.

This supports one statement: through ImageCaptureCore on iOS 27.0.1, the X-T50 answered `0x2001` to the three-byte form `01 00 00` followed by 19 bank-setting writes, and the bank then answered `01 00 00`. On the same body and day, the one-byte form `00` with setting writes after it left the old name through ImageCaptureCore ([client restore](../xt50-20261019-125007/README.md)), and cleared the name over direct USB ([setting-write run](../xt50-20261019-133848/README.md)). The package doesn't establish what ImageCaptureCore sends on the wire for either form, what the camera stores internally, or persistence across a power cycle, which wasn't tested. The trace starts at `2026-10-19T18:05:42Z`. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261019-140542/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-X-T50-20261019-1405.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and all three exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction/privacy checks do not independently prove a hardware observation occurred. The derivative is not a lossless backup.
