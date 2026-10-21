# GFX100S September records

A GFX100S owner tested the maintainers' iOS client, Fuji Cookbook, in three sessions in September 2026, from iPadOS 26.3 through ImageCaptureCore, and exported ten camera reports. The owner agreed to their publication. This note connects the ten [sanitized packages](README.md#available-owner-report-packages) to the record's GFX100S claims, and lists the claims they don't cover. The [source inventory](gfx100s-september-sources.json) hashes the ten reports, the problem reports and Camera Test result exported beside them, and the JPEG pair from 2026-09-29.

## How the reports are built

Each camera report holds the client's trace of its connection at export, and the client's own records: the bank reads, a property sweep, push records, guided-test steps and menu comparisons, profile harvests, and notes. The records carry forward from report to report, so a later report holds comparisons and pushes from sessions whose transactions no report traces, each with its own timestamp. A package keeps every traced transaction, and the records only through an allowlist; [the owner-report section of the index](README.md#available-owner-report-packages) describes what's omitted.

Where a record says what the camera's menu showed, the owner read the menu and the client recorded it: a comparison row that matches means the owner confirmed it, and `ownerReportedCamera` is what the owner entered where it differed. These are owner observations as the client recorded them, not photographs.

## Packages

| Package | Local time, 2026 | Client build, firmware | Trace | Covers |
|---|---|---|---:|---|
| [`gfx100s-20260915-181130`](gfx100s-20260915-181130/README.md) | Sep 15, 18:11 | 2, fw 1.32 | 114 | Two read passes before the firmware update, with every bank descriptor; the selector at 7 |
| [`gfx100s-20260915-194552`](gfx100s-20260915-194552/README.md) | Sep 15, 19:45 | 3, fw 2.13 | 244 | Six banks read, bank 7 refused, the six-bank menu comparison, the grain probe |
| [`gfx100s-20260915-195437`](gfx100s-20260915-195437/README.md) | Sep 15, 19:54 | 3, fw 2.13 | 237 | The write pass: the trial on C2 after a power cycle, its menu comparison, and the restore |
| [`gfx100s-20260917-211657`](gfx100s-20260917-211657/README.md) | Sep 17, 21:16 | 6, fw 2.13 | 171 | A RAF upload and the profile read after it |
| [`gfx100s-20260917-215104`](gfx100s-20260917-215104/README.md) | Sep 17, 21:51 | 6, fw 2.13 | 384 | The same first 171 rows, then DR400 pushes to C2, C3 and C4 |
| [`gfx100s-20260929-221826`](gfx100s-20260929-221826/README.md) | Sep 29, 22:18 | 8, fw 2.13 | 165 | Six banks read; C1 at D-Range Priority Auto; the 2026-09-19 history |
| [`gfx100s-20260929-222001`](gfx100s-20260929-222001/README.md) | Sep 29, 22:20 | 8, fw 2.13 | 167 | The same, with C2's 2026-09-30 comparison |
| [`gfx100s-20260929-225137`](gfx100s-20260929-225137/README.md) | Sep 29, 22:51 | 8, fw 2.13 | 165 | The same, with the 2026-09-30 refusal of `0xD191` on C1 |
| [`gfx100s-20260929-231523`](gfx100s-20260929-231523/README.md) | Sep 29, 23:15 | 8, fw 2.13 | 165 | The same, with C1's menu read as OFF in yellow |
| [`gfx100s-20260929-231728`](gfx100s-20260929-231728/README.md) | Sep 29, 23:17 | 8, fw 2.13 | 167 | The same, with C2's last comparison |

A package's identifier is the report's `updatedAt` in the owner's local time, UTC−4, which the archive file names use. The 2026-09-29 reports carry the owner's own file labels ("C1 PROPERTY REPORT", "C2 REPORT WITH DIAGNOSTIC MODE", and so on). The labels don't change what the client traced: every one of those property sweeps reads bank 1.

## Claims and their packages

| Record claim | Where it is | Package and rows |
|---|---|---|
| Firmware 1.32, then 2.13 on the same body | [Transport](../docs/01-transport.md) | DeviceInfo in [`181130`](gfx100s-20260915-181130/README.md) and [`194552`](gfx100s-20260915-194552/README.md) |
| Image Size `16` read where the selector was parked, without a select | [Encodings](../docs/03-encodings.md) | [`181130`](gfx100s-20260915-181130/README.md), rows 2 and 10 |
| Bank descriptors refused with `0x200A`; `0xD183`'s descriptor answers | [Transport](../docs/01-transport.md) | [`181130`](gfx100s-20260915-181130/README.md), every `0x1014` row |
| Six banks; selecting 7 answers `0x200A` | [Custom banks](../docs/04-custom-slots.md#how-many-banks) | [`194552`](gfx100s-20260915-194552/README.md) and [`195437`](gfx100s-20260915-195437/README.md), row 164 |
| Every bank answers every property; Image Size `14`, Image Quality `2`, `0xD1A5` `14` | [Camera bodies](../docs/07-cameras.md#gfx100s) | The bank pass in every fw 2.13 package |
| Six banks compared with the menu, 12 rows each, no differences; DR Auto `0xFFFF`, NR `0x8000`, Fluorescent 2 `0x8002` with R−2/B−2, sharpness −20 | [Camera bodies](../docs/07-cameras.md#gfx100s) | [`194552`](gfx100s-20260915-194552/README.md): C1's reads and the client's comparison |
| Grain writes refused at `0`, `6`, `7`, `8`; `2`→`1` reads `6`, `5`→`1` reads `7` | [Encodings](../docs/03-encodings.md) | [`194552`](gfx100s-20260915-194552/README.md), rows 223–244 |
| The write pass: settings and name persisted across a power cycle, 12 rows matched, the photo matched | [Camera bodies](../docs/07-cameras.md#gfx100s), [platform notes](../docs/09-platform-notes.md) | [`195437`](gfx100s-20260915-195437/README.md): C2's reads after the power cycle and the client's write-pass record |
| WC +2 / MG −1 as `0x0014` / `0xFFF6` | [Encodings](../docs/03-encodings.md) | [`195437`](gfx100s-20260915-195437/README.md), C2's reads at rows 37–38 |
| `0xD1A5` refuses writes, even of its current value | [Custom banks](../docs/04-custom-slots.md) | [`195437`](gfx100s-20260915-195437/README.md), row 213 |
| The 325 ms name write belongs to the restore | [Camera bodies](../docs/07-cameras.md#gfx100s) | [`195437`](gfx100s-20260915-195437/README.md), row 192 |
| A rollback saved `6`, tested `5`, wrote `1` and read `7` | [Encodings](../docs/03-encodings.md), [custom banks](../docs/04-custom-slots.md) | [`195437`](gfx100s-20260915-195437/README.md): the trial push record and row 221 |
| `0xD185` answers `0x2002` until a RAF is uploaded; 621 bytes, 28 parameters, `FF149502`, table at `0x1FD` | [Conversion profile](../docs/06-conversion-profile.md) | [`211657`](gfx100s-20260917-211657/README.md), rows 166–171 |
| A 208,071,296-byte RAF in 5.392 s; no handles before or after | [RAW conversion](../docs/05-raw-conversion.md), [transport](../docs/01-transport.md) | [`211657`](gfx100s-20260917-211657/README.md), rows 167–170 |
| `0x1FD` scored 5, `0x201` 3, `0x1F9` 2 | [Conversion profile](../docs/06-conversion-profile.md) | [`211657`](gfx100s-20260917-211657/README.md): the client's harvest record |
| DR400 accepted on C2 and refused on C3 and C4, with DR100 and D-Range Priority Off on all three | [Custom banks](../docs/04-custom-slots.md#iso-gating) | [`215104`](gfx100s-20260917-215104/README.md), rows 202, 273 and 344 |
| C1 and C2 held `0x8000`; the menu showed C2 as AUTO and C1 as OFF | [Custom banks](../docs/04-custom-slots.md#the-d-range-priority-interlock) | The client's 2026-09-19 comparisons, carried by every 2026-09-29 package |
| A write to `0xD191` on C1 refused again | [Custom banks](../docs/04-custom-slots.md#the-d-range-priority-interlock) | The client's push records from 2026-09-19 and 2026-09-30 |
| Warm `GetDeviceInfo` 5 ms; accepted bank-setting writes 67–135 ms, with 5 of 81 slow at 344–356 ms | [Transport](../docs/01-transport.md), [write timing](write-timing.md) | `durationMs` in every ledger; each package's `findings.json` summarizes the write durations, and [`write_timing.py`](../tools/write_timing.py) recomputes the figures |

## What the packages don't cover

- The 261-byte `GetDeviceInfo` in storage mode. It comes from an app log in a 2026-09-15 problem report, not from a camera report; every packaged report gives 601 bytes. The problem reports stay private, because their app logs aren't reviewed line by line.
- The power-cycled body taking longer to reappear than the client's reconnect attempts allowed, which also rests on the app logs.
- The ISO of any bank. The client doesn't read ISO, so the base-ISO and ISO 800 statements in [the D-Range Priority interlock](../docs/04-custom-slots.md#the-d-range-priority-interlock) rest on the owner's reports outside these files.
- The 2026-09-19 session's transactions. Its comparisons and pushes survive only as client records in the later reports.
- The JPEG pair from 2026-09-29. Its EXIF carries the camera's serial number and GPS coordinates, and the frames are the owner's photographs, so it isn't published; [RAW conversion](../docs/05-raw-conversion.md) records the statistics measured on it.
- The 2026-10-18 menu photographs, which the [menu-range note](gfx100s-monochromatic-color-menu.md) transcribes.

The bank-name writes in these traces took 325 ms ([`195437`](gfx100s-20260915-195437/README.md), row 192) and 103, 329, and 103 ms ([`215104`](gfx100s-20260917-215104/README.md), rows 199, 270 and 341). The two 103 ms writes are as fast as a bank-setting write, and the 325 and 329 ms writes are the occasional slow writes that [write timing](write-timing.md) describes. [Transport](../docs/01-transport.md) gives both ranges.
