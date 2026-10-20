# X-T50 October 19 empty-name run: sanitized evidence

This package contains a deterministic, allowlisted derivative of the `bankprobe-20261019-102738.json` run on X-T50 firmware 1.32, bank C7: one write of the one-byte empty PTP string to `0xD18D` on a named bank, and the two name reads after it. No bank setting was written, and the probe ran with `--no-restore`, so the name was not put back. It answers the empty-name question that the October runs left open; the [evidence index](../README.md) explains the files.

The original's SHA-256 is `fa0318589a7caa4b7d6e461da9649e519b36eea4f2b9101043d804f917fc2dc0`; it stays in the maintainers' private archive at revision `c2e865e72c451688851a4c6706739a018c524f7a`, at the path the [manifest](manifest.json) records, and the [source inventory](../xt50-20261019-sources.json) lists the archive directory's three files. The run has no transcript and no probe findings of its own.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 39 original entries in order: 38 operation rows and one host selector-restored event. |
| [`findings.json`](findings.json) | The reviewed name write and its two readbacks with source indices, and the maintainer's menu observation. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, counts, conditions, omissions, and hashes of both exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [package exporter](../bankprobe_package.py); rejects any original with a different hash. |

The ledger retains 31 scalar payload fields (the selector and the 23 bank reads) and the three `0xD18D` payloads that hold no name, kept as `emptyNameOutHex` and `emptyNameInHex`; it omits two payload fields, the bank's initial name and DeviceInfo. All 38 operations record `0x2001`. Responses are from a host-generated report without independently correlated bus provenance. The original has no top-level before/after snapshot pair; no snapshot artifact is invented.

This package is the reason the shared exporter keeps exactly two `0xD18D` payloads, `00` and `010000`: neither can carry a name, and the write and its readbacks are the evidence. Every other `0xD18D` payload stays omitted, as in the October packages.

## The write and its readbacks

| Step | Source evidence | Result |
|---|---|---|
| Select C7 | Write 3, read 4 | `0700`, both `0x2001`. |
| Initial name | Read 5 | A non-empty name, response `0x2001`; contents omitted. |
| Bank settings | Reads 6–28 | The 23 bank settings, all `0x2001`; none written in this run. |
| Reselect C7 | Write 29, reads 30 and 31 | `0700`, all `0x2001`. |
| Write the empty name | Write 32 | Payload `00`, the standard one-byte empty PTP string; response `0x2001`. |
| Read the name | Reads 33 and 34 | Payload `010000`, a count of 1 and the NUL, both `0x2001`; not byte-equal to the write. |
| Restore the selector | Write 35, read 36, event 37 | Back to bank 1. |
| CloseSession | 38 | `0x2001`. |

The readback is the three-byte form FilmKit's issue #12 log shows for a never-named X-T50 bank (firmware 1.31), so an emptied name and a never-set one read alike. After the run the maintainer reported the camera's menu labeling the bank **CUSTOM 7** with a blank name editor. That observation comes from the maintainer's message, not from the log or a photograph, and `findings.json` labels it so.

This supports one statement: the X-T50 accepts an empty-name write and afterward answers the unnamed form. It doesn't establish what the camera stores internally, whether the bank then counts as unprogrammed, behavior on another body, or persistence across a power cycle, which wasn't tested. The local start time is `2026-10-19T10:27:38`, without offset/timezone. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261019-102738/export.py \
  ARCHIVE_DIR/bankprobe-20261019-102738.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and both exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction/privacy checks do not independently prove a hardware observation occurred. The derivative is not a lossless backup.
