# Evidence index

This folder holds the record's own hardware evidence in sanitized form: the [report schema](report-schema.md) for contributed USB observations, the [GFX100S menu photographs note](gfx100s-monochromatic-color-menu.md), and the seven X-T50 bankprobe packages, two client-report packages, and 29 client-trace packages listed in [Available X-T50 packages](#available-x-t50-packages), and the eleven GFX100S and X-T20 packages listed in [Available owner-report packages](#available-owner-report-packages). The [write-timing note](write-timing.md) draws on every published client trace. [Open questions](../docs/open-questions.md) lists the experiments still wanted and [errata](../docs/errata.md) the corrections made; this page covers what is published, how to read it, and how to add a package.

Original availability and claim verification are separate. A published original establishes what was recorded, not a proposed mechanism, a missing camera condition, or behavior on another body. Evidence tags keep their meanings.

Keep immutable originals in a backed-up private archive outside this repository and its working checkout. Record the original filename and a file SHA-256 in the private inventory; never retain serials, hashes of serials, physical-device identifiers, bank names, personal paths, photographs, or raw captures in public exports. The one exception is the keyed camera identifier, marked `hmac-sha256`, that the maintainers' client has recorded since its builds of 2026-10-15: HMAC-SHA256 of the serial under a random key that never leaves the reporting phone, so a guessed serial can't be checked against it. A manifest may carry it; an unkeyed hash, which a guessed serial can be checked against, is never published. A file hash identifies the evidence bytes, not a device. A bank backup is never inventoried, even by hash: its values are public in the package, so a hash over the file would stand in for the bank name. See [contribution privacy](../CONTRIBUTING.md#privacy).

## Available X-T50 packages

The five October packages derive from hash-pinned originals in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582` ([inventory](xt50-october-sources.json)), the October 19 10:27 bankprobe package from revision `c2e865e72c451688851a4c6706739a018c524f7a` ([inventory](xt50-20261019-sources.json)), the 12:50 client-report package from revision `2a3d1221d130e8d7cddf02f9f746dfe8adfa147b` ([inventory](xt50-20261019-client-sources.json)), the October 19 13:38 bankprobe package from revision `1d491480ea2e108d45f9e9d0eea0d241ee750e13` ([inventory](xt50-20261019-133848-sources.json)), and the 14:05 client-report package from revision `50dabec6c251f39d30a6c962daafd4c71c7bde7d` ([inventory](xt50-20261019-140542-sources.json)). An inventory covers one archive revision and directory, which is why there are five. Each package preserves source-array order, separates response outcome from state verification, documents omissions and unknown conditions, and provides a deterministic exporter that checks the original's hash. The six later bankprobe packages share [export helpers](bankprobe_package.py); the client-report packages have their own [exporter](client_report_package.py), which reuses them. These are historical evidence exports, not new camera tests or recovery backups.

| Package | Selected evidence | Source rows retained |
|---|---|---:|
| [October 15, 22:48:19](xt50-20261015-224819/README.md) | Initial menu/DR/toning/HEIF suite and numeric before/after snapshots | 1,692 |
| [October 15, 23:24:41](xt50-20261015-232441/README.md) | Additional menu mappings, ISO and HEIF comparisons, partial Digital Tele-Converter trial, no-name persistence control | 1,888 |
| [October 16, 09:40:28](xt50-20261016-094028/README.md) | Four name-timing conditions with normalized operator observations | 134 |
| [October 16, 09:56:11](xt50-20261016-095611/README.md) | Two changed-value RESET controls and an item-entry comparison | 221 |
| [October 16, 10:07:52](xt50-20261016-100752/README.md) | Dot observation and instructed power-cycle/readback case, including a name write | 125 |
| [October 19, 10:27:38](xt50-20261019-102738/README.md) | Empty-name write to `0xD18D` on a named bank and the two reads after it | 39 |
| [October 19, 12:50:07](xt50-20261019-125007/README.md) | Client restore through iOS ImageCaptureCore: an empty-name write to `0xD18D`, 20 bank-setting writes, and the final name read | 339 |
| [October 19, 13:38:48](xt50-20261019-133848/README.md) | Both empty-name encodings on a named bank, each followed by a Film Simulation write and its reversal, with the name read after each write | 145 |
| [October 19, 14:05:42](xt50-20261019-140542/README.md) | Client push and undo through iOS ImageCaptureCore: the three-byte empty name `01 00 00`, 19 bank-setting writes, and the final name read | 325 |
| [September 6 – October 19, 29 client traces](xt50-client-traces/README.md) | Trace-only packages of the client's other X-T50 camera reports: every transaction with its response and host-measured duration, without the client's records; the basis of the [write-timing note](write-timing.md) | 9,155 |

Times are local run times. The bankprobe logs carry no offset and their timezone is unknown; the client reports record UTC, and their rows give each trace start, `16:50:07Z` and `18:05:42Z`, in the maintainers' local time (UTC−4) that their archive file names use. The [October records note](xt50-october-records.md) connects these packages to their original runs and to six unpackaged runs, and gives the source-array position of each cited write and read. The October 16 and 19 packages have no before/after snapshot pair because their originals have none.

### Reading a package

Each package has `transactions.jsonl` (every entry of the original `transactions` array in order, one JSON object per line), `findings.json` (typed numeric details of the selected source findings, with the probe's verdict prose and `ok` flags omitted), `manifest.json` (source and artifact hashes, coverage counts, conditions, omission rules, and exporter hashes), and `export.py` (the run-specific exporter). The October 15 packages also have `snapshots.json`, the seven before and seven after bank snapshots. The client-report packages' rows are the commands the client handed to ImageCaptureCore, so the following bullets about bankprobe logs don't all apply to them; the [first one's README](xt50-20261019-125007/README.md#files-and-coverage) gives the differences.

- `sourceIndex` is the zero-based index in the original `transactions` array; its JSONL line is `sourceIndex + 1`. PTP transaction IDs repeat after reconnects and aren't unique identifiers. `camera_lost` and `camera_back` are host-recorded events; they don't establish why a disconnect occurred or that a power cycle happened. An `experiment_context` event keeps only the operator's AUTO UPDATE answer as bankprobe normalized it, and a `bank_restore_verification` event keeps each field's cleanup status without its value.
- Transactions with no recorded completion keep `response: null`, `outcome: "outcome_unknown"`, and whether a transport error was recorded; the error text is omitted. An absent response isn't a refusal, a success, or evidence of camera liveness. Responses come from a host-generated report, not an independently correlated bus capture.
- Payload strings are raw bytes in source order, interpreted little-endian: `6400` is unsigned 100 and `ffff` unsigned 65535, whose signed or sentinel meaning depends on the property. Snapshot and finding values are unsigned JSON integers. Only one-to-four-byte payloads on the selector, bank, and live `0xD1A5` allowlist survive, plus the two `0xD18D` payloads that hold no name (the one-byte empty string `00`, and the count-plus-NUL `010000` an unnamed bank answers), kept as `emptyNameInHex`/`emptyNameOutHex`; bank names and every other `0xD18D` payload, DeviceInfo, `0xD186`/`0xD187` payloads, identity fields, command lines, paths, error prose, and the original verdicts are omitted, while transaction headers and outcomes stay visible.
- Bank settings are kept separate from live `0xD1A5`, which was sampled while a bank was selected and isn't a 24th bank field.
- The originals carry local timestamps for snapshots and reconnect events but none per transaction, and no reliable connection identifiers, so the packages use this documented companion format rather than inventing fields to satisfy [report schema v1](report-schema.md). They don't establish command timing, capture completeness, pixels, independent power telemetry, or persistence across a verified restart.
- USB mode, **AUTO UPDATE CUSTOM SETTING**, timezone, lens state, and ISO aren't established by the originals; a prompted setting is an instruction, not an observation of the camera's state. Operator observations in `findings.json` are normalized readings of the operator's responses with pointers into the original JSON; they aren't menu photographs or telemetry.

To verify a package against its original, run its `export.py` with the original's path and `--check`; the exporter refuses an original whose hash differs or that sits inside the checkout, and never modifies or copies it. `python3 -B -m unittest discover -s tests -p 'test_evidence_packages.py' -v` runs the public integrity and privacy checks without any original.

## Available owner-report packages

Two camera owners sent the maintainers reports from their own bodies and agreed to their publication: a GFX100S owner's ten camera reports from three sessions in September 2026, and an X-T20 owner's app-log excerpt, received on 2026-09-14. These packages derive from hash-pinned originals in the maintainers' private archive at revision `a9c1bf66fd0ad7f7383540c0d35b4629f3c948a9` ([GFX100S inventory](gfx100s-september-sources.json), [X-T20 inventory](xt20-sources.json)). The [GFX100S September records note](gfx100s-september-records.md) connects the GFX100S packages to the record's claims and lists the claims they don't cover. Their evidence tags stay `[Owner report]`: a package makes the report inspectable, and doesn't turn the owner's observation into a measurement.

| Package | Selected evidence | Source rows retained |
|---|---|---:|
| [X-T20, undated, 17:28:51](xt20-undated-172851/README.md) | DeviceInfo in four connections; the bank block, `0xD185`, and `0xD183` in the client's property report | 150 lines |
| [GFX100S, September 15, 18:11:30](gfx100s-20260915-181130/README.md) | Two read passes at fw 1.32, with every descriptor; the selector at 7 | 114 |
| [GFX100S, September 15, 19:45:52](gfx100s-20260915-194552/README.md) | Six banks read, bank 7 refused, the six-bank menu comparison, the grain probe | 244 |
| [GFX100S, September 15, 19:54:37](gfx100s-20260915-195437/README.md) | The write pass: the trial on C2 after a power cycle, its menu comparison, and the restore | 237 |
| [GFX100S, September 17, 21:16:57](gfx100s-20260917-211657/README.md) | A RAF upload and the 621-byte profile read after it | 171 |
| [GFX100S, September 17, 21:51:04](gfx100s-20260917-215104/README.md) | The same first 171 rows, then DR400 pushes accepted on C2 and refused on C3 and C4 | 384 |
| [GFX100S, September 29, 22:18:26](gfx100s-20260929-221826/README.md) | Six banks read, C1 at D-Range Priority Auto, and the client's 2026-09-19 comparisons | 165 |
| [GFX100S, September 29, 22:20:01](gfx100s-20260929-222001/README.md) | The same, with C2's 2026-09-30 comparison | 167 |
| [GFX100S, September 29, 22:51:37](gfx100s-20260929-225137/README.md) | The same, with the 2026-09-30 refusal of `0xD191` on C1 | 165 |
| [GFX100S, September 29, 23:15:23](gfx100s-20260929-231523/README.md) | The same, with C1's menu read as OFF in yellow | 165 |
| [GFX100S, September 29, 23:17:28](gfx100s-20260929-231728/README.md) | The same, with C2's last comparison | 167 |

Times are the owners' local times: the X-T20 log's first line, which carries no date, and each GFX100S report's `updatedAt` at UTC−4, the offset its archive file names use. Owner-report packages differ from the maintainers' own in four ways.

- The GFX100S reports are versions 4 and 5 of the client report the X-T50 client-report packages use, and their `transactions.jsonl` comes from the same [exporter](client_report_package.py), unchanged. Each package adds `client-records.json`: the client's own records, through an allowlist. They are the bank reads, the property sweep, push records, guided-test steps and menu comparisons, profile harvests, and notes. A string survives only from a reviewed enumeration, a strict pattern, or the client's display text for a camera setting, and an unreviewed field stops the export. The records carry forward from report to report, each with its own time, so a report can hold records of a session that no report traces. `findings.json` holds mechanical observations over the trace and the run's reviewed findings, with row pointers.
- Owner reports carry identifiers: the client's serial hash, unkeyed in every GFX100S report and so as good as the serial, because a serial is short enough to recover from its hash; the host's device model; guided-test session identifiers; and bank and recipe names, including names the property sweep read as raw `0xD18D` bytes. All are omitted. Before writing, the [shared exporter](owner_report_package.py) searches every output for each of them, as plain text, as JSON escapes, and as the UTF-16 hexadecimal a PTP string carries, and stops on a hit. Name lengths aren't kept.
- The X-T20 package's `log.jsonl` has one row per line of the original. Each line must match one of 30 reviewed line forms or the export stops, and an output holding a hexadecimal run longer than a PTP code is refused. The log holds no serial number and no serial hash.
- Some owner files aren't published: the GFX100S problem reports, whose app logs aren't reviewed line by line; the JPEG pair from 2026-09-29, whose EXIF carries the camera's serial number and GPS coordinates; and the menu photographs, which [their note](gfx100s-monochromatic-color-menu.md) transcribes.

`python3 -B -m unittest discover -s tests -p 'test_owner_report_packages.py' -v` runs the integrity and privacy checks for these packages without any original.

## Requests to upstream authors

These are work items, not messages already sent. When you add a later clarification, preserve the pinned revisions in [SOURCES](../SOURCES.md#inspected-revisions-and-source-paths) so the change in evidence stays reviewable.

- fujifilm-ptp-recipes: its [live verification report](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/current-shooting-state.md#L112-L123) says all 23 live codes were written and read back changed, while its [status page](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/protocol-status.md#L116-L121) says live Lens Modulation Optimizer `0xD34D` was read and never written. Ask for the run chronology, firmware, and the `0xD34D` before, written, and read-back values with the response. Until then both accounts stay visible; see [errata](../docs/errata.md#x-h2-live-write-coverage-conflicts-within-the-source).
- Research follow-ups that don't block publication: ExifTool's originating forum discussions and sample images behind several FujiFilm tag definitions (topics 5223, 10800, 14319, and the later pages of 9607 couldn't be read in full), and the version, hashes, and method behind fujifilm-ptp-recipes' X RAW Studio binary analysis. Both are cited as published interpretations; the record says that their originating measurements weren't repeated here.
- File the [corrections to published sources](../docs/errata.md) upstream as issues; FilmKit doesn't accept pull requests.

## Adding and closing an evidence package

1. Give the package an identifier of its own (the run's local start time, as described earlier).
2. Record the observation date separately from the dates the archive was read and analyzed.
3. Pin the archive revision and calculate a fresh SHA-256 of the original before transforming it.
4. Record exactly which original entries support each included observation:
   - Keep response outcome, state verification, menu confirmation, persistence, and pixel comparison separate.
   - Disclose dropped operations and trace coverage.
   - Leave missing firmware, mode, AUTO UPDATE, or operator confirmation unknown.
5. Produce an allowlisted public derivative and a method note. Keep the immutable original outside the checkout; the derivative isn't a recovery backup.
6. Inspect the export for personal data.
7. Validate schema-compatible reports with `tools/validate_evidence.py`.
8. Reconcile the package with any earlier summary of the same run, and record agreement and differences, including corrected verdicts, without changing the original bytes.
9. Hash the exported artifacts and keep a reproducible generation command or script.
10. Link the package here and update the affected chapters, [SOURCES](../SOURCES.md), [errata](../docs/errata.md), and [open questions](../docs/open-questions.md) only where the new evidence changes what they say.
