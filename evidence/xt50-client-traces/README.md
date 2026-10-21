# X-T50 client traces, September–October 2026: sanitized evidence

These 29 packages are deterministic, allowlisted derivatives of camera reports the maintainers' iOS client exported from the maintainers' X-T50 on firmware 1.32, between 2026-09-06 and 2026-10-19. The client was a debug build, numbered 1 to 12, on iOS 26.6.1 to 27.0.1, through ImageCaptureCore. With the [12:50](../xt50-20261019-125007/README.md) and [14:05](../xt50-20261019-140542/README.md) client-report packages, which already publish the two other reports, every camera report in the archive's X-T50 directory is now public as a trace. The [write-timing note](../write-timing.md) uses all 31.

These are trace packages. Each keeps one report's PTP transactions, in order, with their responses and the client's host-measured durations, plus mechanical observations over them. They carry no run-specific review: the client's own records aren't projected at all, so its bank reads, pushes, guided tests, develops, property sweeps, and notes stay private. The two earlier packages are reviewed: they document an empty-name restore and undo.

The originals stay in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9`. The [source inventory](../xt50-client-traces-sources.json) and each package's manifest give every original's path and SHA-256.

## Files and coverage

Each package folder holds three files, and one [exporter](export.py) serves them all:

| File | Contents |
|---|---|
| `transactions.jsonl` | Every traced transaction in order, none dropped by the client, through the [client-report ledger](../client_report_package.py) the 12:50 and 14:05 packages use. |
| `findings.json` | Mechanical observations from the [shared trace observer](../owner_report_package.py): every selector operation and bank write with its addressed bank, response and duration; descriptor responses by property; profile reads; object operations; the spread of accepted write durations; and a count of property reads with the slowest. |
| `manifest.json` | Source and derivative hashes, coverage counts, client build and system version, the keyed camera identifier where the report carries one, unknown conditions, omissions, and the hashes of the exporter and its three modules. |

A ledger keeps transaction headers, response codes, durations, and the one-to-four-byte payloads of the selector, the 23 bank settings, and the live `0xD1A5`; and of `0xD18D`, only the two encodings of an empty name. It omits every other payload and its length, including bank names, DeviceInfo, descriptors, conversion profiles, and objects.

The six packages from 2026-10-15 on carry the client's keyed camera identifier (`hmac-sha256`) in their manifests, the same value as the 12:50 and 14:05 packages: HMAC-SHA256 of the serial under a random key that never leaves the reporting phone, so a guessed serial can't be checked against it. The 23 earlier reports were made by builds that recorded an unkeyed hash, which a guessed serial can be checked against; their manifests record no identifier. The packages omit every unkeyed hash, the host device's model, the USB identifiers, and the client's connection, session, run, and result identifiers. Before writing, the exporter searches every output for each bank and recipe name and each identifier the original holds, as plain text, as JSON escapes, and as UTF-16 hexadecimal, and stops on a hit. The manifests record how many private strings each check covered, 30 to 61 per report.

| Package | Report version | Client build | iOS | Trace rows | Writes | Name writes | Upload |
|---|---:|---:|---|---:|---:|---:|---|
| [`xt50-20260906-180652`](xt50-20260906-180652/manifest.json) | 2 | 1 | 26.6.1 | 183 | 7 | 0 | |
| [`xt50-20260906-182230`](xt50-20260906-182230/manifest.json) | 2 | 1 | 26.6.1 | 183 | 7 | 0 | |
| [`xt50-20260906-191557`](xt50-20260906-191557/manifest.json) | 2 | 1 | 26.6.1 | 190 | 7 | 0 | |
| [`xt50-20260906-195112`](xt50-20260906-195112/manifest.json) | 2 | 1 | 26.6.1 | 190 | 7 | 0 | |
| [`xt50-20260906-200420`](xt50-20260906-200420/manifest.json) | 2 | 1 | 26.6.1 | 190 | 7 | 0 | |
| [`xt50-20260907-163145`](xt50-20260907-163145/manifest.json) | 2 | 1 | 26.6.1 | 694 | 168 | 7 | |
| [`xt50-20260914-200137`](xt50-20260914-200137/manifest.json) | 4 | 2 | 26.6.2 | 247 | 8 | 0 | |
| [`xt50-20260914-203438`](xt50-20260914-203438/manifest.json) | 4 | 2 | 26.6.2 | 257 | 10 | 0 | yes |
| [`xt50-20260914-203812`](xt50-20260914-203812/manifest.json) | 4 | 2 | 26.6.2 | 265 | 33 | 1 | |
| [`xt50-20260914-205600`](xt50-20260914-205600/manifest.json) | 4 | 2 | 26.6.2 | 257 | 10 | 0 | yes |
| [`xt50-20260914-205836`](xt50-20260914-205836/manifest.json) | 4 | 2 | 26.6.2 | 265 | 33 | 1 | |
| [`xt50-20260914-210459`](xt50-20260914-210459/manifest.json) | 4 | 2 | 26.6.2 | 281 | 23 | 0 | yes |
| [`xt50-20260914-210650`](xt50-20260914-210650/manifest.json) | 4 | 2 | 26.6.2 | 263 | 30 | 1 | |
| [`xt50-20260915-225954`](xt50-20260915-225954/manifest.json) | 5 | 4 | 26.6.2 | 700 | 167 | 7 | |
| [`xt50-20260920-165222`](xt50-20260920-165222/manifest.json) | 5 | 8 | 26.6.2 | 1200 | 314 | 14 | |
| [`xt50-20260920-170753`](xt50-20260920-170753/manifest.json) | 5 | 8 | 26.6.2 | 340 | 53 | 2 | |
| [`xt50-20260920-171710`](xt50-20260920-171710/manifest.json) | 5 | 8 | 26.6.2 | 266 | 30 | 1 | |
| [`xt50-20260920-173842`](xt50-20260920-173842/manifest.json) | 5 | 8 | 26.6.2 | 267 | 31 | 1 | |
| [`xt50-20261003-132005`](xt50-20261003-132005/manifest.json) | 6 | 9 | 26.6.2 | 255 | 9 | 0 | |
| [`xt50-20261003-133415`](xt50-20261003-133415/manifest.json) | 6 | 9 | 26.6.2 | 279 | 33 | 1 | yes |
| [`xt50-20261003-143543`](xt50-20261003-143543/manifest.json) | 6 | 9 | 26.6.2 | 279 | 33 | 1 | yes |
| [`xt50-20261003-214040`](xt50-20261003-214040/manifest.json) | 6 | 9 | 26.6.2 | 255 | 9 | 0 | |
| [`xt50-20261003-222000`](xt50-20261003-222000/manifest.json) | 6 | 9 | 26.6.2 | 353 | 57 | 2 | yes |
| [`xt50-20261015-172015`](xt50-20261015-172015/manifest.json) | 6 | 12 | 27.0.1 | 200 | 9 | 0 | yes |
| [`xt50-20261017-175208`](xt50-20261017-175208/manifest.json) | 6 | 12 | 27.0.1 | 279 | 33 | 1 | yes |
| [`xt50-20261018-173731`](xt50-20261018-173731/manifest.json) | 6 | 12 | 27.0.1 | 301 | 37 | 1 | yes |
| [`xt50-20261018-174411`](xt50-20261018-174411/manifest.json) | 6 | 12 | 27.0.1 | 258 | 30 | 1 | |
| [`xt50-20261019-101935`](xt50-20261019-101935/manifest.json) | 6 | 12 | 27.0.1 | 258 | 30 | 1 | |
| [`xt50-20261019-102134`](xt50-20261019-102134/manifest.json) | 6 | 12 | 27.0.1 | 200 | 10 | 0 | yes |

A package's identifier is the report's `generatedAt` in the maintainers' local time, UTC−4, the clock the archive file names use; where a report records its trace's start, the two are the same. Reports from one evening often ran the same scripted steps, so some traces have the same shape, but no trace repeats another: their durations differ row by row. "Writes" counts every `SetDevicePropValue`, refusals included, and "Upload" marks a RAF upload in the trace.

## What they establish, and what they don't

Each trace is the client's record of one connection: the commands it handed to ImageCaptureCore, the responses it got back, and how long each took on the host. That supports the [write-timing note](../write-timing.md), and it lets any later claim about these runs point to a sequence number.

A trace doesn't observe the USB wire, so a duration includes host-side time the camera didn't spend. A trace doesn't record what the camera's menu showed, and it doesn't record the USB mode, AUTO UPDATE CUSTOM SETTING, ISO, lens, or image format. Which recipe a push carried, what a develop produced, and what the operator saw are in the client's records, which these packages leave out. The bank settings a push wrote are in the ledger as scalars, so they can be read, but the packages don't interpret them.

## Reproduce and verify

Keep the immutable originals outside the checkout. From the reference repository root, pass any one of the 29 originals; the exporter finds its package by the original's hash:

```bash
python3 -B evidence/xt50-client-traces/export.py \
  ARCHIVE_DIR/fuji-cookbook-camera-report-X-T50-20260920-1652.json --check
```

To regenerate a package's three artifacts, omit `--check`; to write them elsewhere, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_client_trace_packages.py' -v
```

Evidence text and data follow the documentation license; the Python exporter and tests are MIT-licensed. Reproduction and privacy checks don't independently prove a hardware observation occurred. The derivatives aren't lossless backups.
