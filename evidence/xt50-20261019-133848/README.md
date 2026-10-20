# X-T50 October 19 empty-name test with setting writes: sanitized evidence

This package contains a deterministic, allowlisted derivative of the `bankprobe-20261019-133848.json` run on X-T50 firmware 1.32, bank C7: the `empty-name` test of [`tools/bankprobe.py`](../../tools/bankprobe.py), over direct USB. For each empty encoding of `0xD18D` in turn, it wrote the encoding to the named bank, wrote a different Film Simulation and then the original one, and read the name after each write. Then it wrote the bank's original name back. The [evidence index](../README.md) explains the files.

The original's SHA-256 is `e53af100187c140dd8654b60f7e21fab8e9044404fb834e2d9e2cd26a4bc1112`; it stays in the maintainers' private archive at revision `1d491480ea2e108d45f9e9d0eea0d241ee750e13`, at the path the [manifest](manifest.json) records. The [source inventory](../xt50-20261019-133848-sources.json) also hashes the run's transcript.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 145 original entries in order: 142 operation rows and three host events. |
| [`findings.json`](findings.json) | The two trials with source indices, the cleanup verification, and the operator's AUTO UPDATE answer. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, counts, conditions, omissions, and hashes of both exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [package exporter](../bankprobe_package.py); rejects any original with a different hash. |

The ledger retains 123 scalar payload fields on the selector, bank, and live `0xD1A5` allowlist and the eight `0xD18D` payloads that hold no name, kept as `emptyNameOutHex` and `emptyNameInHex`. It omits nine payload fields: DeviceInfo, and the bank's name in six reads and two writes. All 142 operations record `0x2001`. The three events are the experiment context, which keeps only the operator's AUTO UPDATE answer, `unknown`; the cleanup verification, which keeps each field's status but not its value; and the selector restore. Responses are from a host-generated report without independently correlated bus provenance.

## The two trials

C7 held a non-empty name and Film Simulation `11` (Classic Chrome) when the trials began. The name's contents are omitted.

| Step | `00` trial | `01 00 00` trial | Result in both |
|---|---|---|---|
| Write the empty encoding | Write 59 | Write 73 | `0x2001`. |
| Read the name | Read 60 | Read 74 | `010000`. |
| Write Film Simulation `2`, read it | 62, 63 | 76, 77 | `0x2001`, reads `2`. |
| Read the name | Read 64 | Read 78 | `010000`. |
| Write Film Simulation `11`, read it | 66, 67 | 80, 81 | `0x2001`, reads `11`. |
| Read the name | Read 68 | Read 82 | `010000`. |
| Write the original name, read it | 70, 71 | 84, 85 | `0x2001`, byte-equal to the initial read 34. |

Before each content write the probe read the selector and found C7; those reads sit between the steps in the preceding table. Cleanup at index 140 found all 24 name and setting fields exact and needed no writes, and the selector was left on C7. CloseSession at 144 answered `0x2001`.

This supports three statements, over direct USB on this body: the one-byte empty string and the three-byte form `01 00 00` are both accepted and leave the bank answering `01 00 00`; a bank-setting write after either doesn't change that; and writing the original name back restores it byte for byte. Bank settings written after an empty name therefore don't explain the [client restore](../xt50-20261019-125007/README.md), where the name read after 20 setting writes was the old one. The two transports remain the difference. This package doesn't establish what ImageCaptureCore sends for a one-byte data phase, what the camera stores internally, or persistence across a power cycle, which wasn't tested. The local start time is `2026-10-19T13:38:48`, without offset/timezone. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261019-133848/export.py \
  ARCHIVE_DIR/bankprobe-20261019-133848.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and both exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction/privacy checks do not independently prove a hardware observation occurred. The derivative is not a lossless backup.
