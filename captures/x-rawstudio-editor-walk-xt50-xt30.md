# X RAW Studio's editor, one setting at a time — X-T50 and X-T30

Sources: the public captures attached to [FilmKit issue #12](https://github.com/eggricesoy/filmkit/issues/12) (`X-T50_Preset Save.pcapng`, an X-T50 at firmware 1.31) and [FilmKit issue #13](https://github.com/eggricesoy/filmkit/issues/13) (`X-T30_Profile_Read`, `X-T30_Preset_Save_PT1`, and `_PT2`, an X-T30 at firmware 2.01), both Windows USBPcap. This transcript comes from an unpublished scratch decoder that recovered the stream after dropped transfers. [`tools/ptpcap.py`](../tools/README.md) reproduces the available public subset with opt-in `--recover`; it validates candidate headers against device/transaction context and reports abandoned containers. For attachment hashes, commands, verified outputs, and unavailable/private inputs, see [Reproducing the public capture analysis](reproduction.md). Recovery is heuristic and doesn't establish complete JPEG pixels. Cells are read at `0x1FD + 4·i`, signed 32-bit little-endian. MakerNotes were read from the downloaded previews with `exiftool -n`. The captures contain their authors' photos and serial numbers; this record links them rather than re-hosting them.

In both captures the author stepped X RAW Studio's editor through one setting at a time, in the order of the settings screens attached to the issue, with a preview conversion (`0xD183 = 0`) after each step. Each profile write therefore differs from the one before it in the cells of that one setting, and the preview's MakerNote shows what the camera did with it. That is a one-variable observation per step, which is what settles a cell.

## The X-T50 walk (issue #12)

Transaction IDs 1108–1743. Each row is one profile write; "cells changed" compares it with the write before.

| tid | Cells changed | Setting, as the author set it |
|--|--|--|
| 1144 | 4: `3` → `2` | Image Quality FINE |
| 1178 | 5: `0` → `−1000` | Push/pull −1 EV |
| 1214 | 8: `1` → `11` | Classic Chrome |
| 1250, 1284 | 9: `4` → `5` → `3` | Grain Strong, then size Small |
| 1320 | 10: `2` → `3` | Color Chrome Effect Strong |
| 1354 | 25: `2` → `3` | Color Chrome FX Blue Strong |
| 1390 | 24: `3` → `2` | Smooth Skin Weak |
| 1426 | 12: `0x8008` → `4`; 15: `5600` → `0` | White balance Custom 1 → Daylight |
| 1462 | 13: `−4` → `3`; 14: `4` → `−2` | WB shift R +3, B −2 |
| 1498 | 16: `0` → `10` | Highlight +1 |
| 1534 | 17: `20` → `0` | Shadow 0 |
| 1570 | 18: `30` → `0` | Color 0 |
| 1606 | 19: `−40` → `−20` | Sharpness −2 |
| 1642 | 20: `0x8000` → `0x4000` | High ISO NR −2 |
| 1680 | 27: `30` → `0` | Clarity 0 |
| 1701 | 21: `2` → `1` | Lens Modulation Optimizer ON |
| 1722 | 22: `2` → `1` | Color Space sRGB |

### What the previews confirm

- Cell 21 is Lens Modulation Optimizer, `1` On / `2` Off. The preview before tid 1701 (GetObject tid 1690) carries `LensModulationOptimizer` Off in its MakerNote; the one after (tid 1711) carries On. Nothing but cell 21 changed between them.
- Cell 22 is Color Space, `1` sRGB / `2` Adobe RGB. The preview before tid 1722 (tid 1711) carries `InteropIndex` R03 (Adobe RGB); the one after (tid 1732) carries R98 (sRGB).
- Cell 4 is Image Quality, `2` FINE / `3` NORMAL, and cell 5 is Exposure Bias in thousandths of an EV: the author's −1 EV is `−1000`.
- Cells 8, 9, 10, 12–20, 24, 25, and 27 move with the setting the record already gives them, with only the cell or cells for that setting changed (the WB-source/mode change involves two cells).

Across every preview decoded from this capture, cell 21 and the MakerNote agree: 3 writes with `1` carry LMO On, 17 with `2` carry Off.

### Additional X-T50 Profile_Read capture

The separate [Profile Read attachment](https://github.com/user-attachments/files/27558954/X-T50_Profile_Read.pcapng.gz) in issue #12 adds a counterexample to the original sample's uniform tail and header values. Its initial profile read (tid 378) is 625 bytes with numParams 29 and IOPCode length byte `8`. X RAW Studio's write (tid 379) is 629 bytes with numParams 29, length byte `9`, and cell 29 = `1`; the camera answers `0x2001` (OK). Its later profile read (tid 408) is 625 bytes with numParams 29 and length byte `9`. All three carry IOPCode `FF189504`. These are complete profile transfers; the surrounding RAW upload and JPEG download are incomplete in the capture. The [hash, commands, and metadata-only reproduction](reproduction.md#additional-x-t50-profile-read-capture) are separate from the four-file editor-walk expectation set.

## The X-T30 walk (issue #13)

The Profile_Read capture: after the upload (tids 38–39), `GetDevicePropValue 0xD185` (tid 43) returns 605 bytes, numParams 24, IOPCode length byte 8, IOPCode `FF159502`. 605 − 4·24 = `0x1FD`, so the table starts where it does on every other body and has 24 cells, 0–23. `0xD184` reads `FF159502,FA159502` (tids 16, 21). X RAW Studio's first write (tid 44) is 629 bytes with numParams 29 and length byte 9, and fills the six cells the body lacks with `0, 1, 0, 0, 2, 1` (cells 24–29) rather than zeros; its later writes zero-extend. The read-back (tid 69) is 605 bytes again.

Preset_Save_PT1 (tids 200–555) holds seventeen profile-write-and-convert cycles and nothing else: no `SetDevicePropValue` other than `0xD185` and `0xD183`, no access to `0xD18C`–`0xD1A5`, no `0xD38C` or `0xD207`, no `GetDevicePropDesc`. PT2 (tids 580–587) is four battery polls, and the 24 transaction IDs missing between the files fit twelve `0xD36A`/`0xD36B` poll pairs at X RAW Studio's 3-second cadence. These supplied captures contain no X-T30 bank write. That observation doesn't prove what every X RAW Studio operation or mode can do on the body.

The walk repeats the X-T50's results on X-Processor 4, with the author stepping the other way:

| tid | Cells changed | Setting |
|--|--|--|
| 493 | 21: `1` → `2` | Lens Modulation Optimizer ON → OFF; the preview goes from On (GetObject tid 483) to Off (tid 504) |
| 514 | 22: `1` → `2` | Color Space sRGB → Adobe RGB; the preview goes from R98 to R03 (tid 525) |

It adds cell 4 `2` → `3` for NORMAL, cell 6 `100` → `400` for DR400, and cell 12 `0x8007` → `0x8008` with cell 15 `5300` → `0` for Kelvin 5300 → Custom 1. Across its previews, 15 writes with cell 21 = `1` carry LMO On and 3 with `2` carry Off. The X-T30's frame, shot with LMO On, reads `1` in cell 21 as shot, and its as-shot preview carries On.

## The live write after a bank save (issue #12)

The same X-T50 capture holds X RAW Studio saving the edited preset to C1 (the transcript in [X RAW Studio saving a bank](x-rawstudio-bank-save-xt50.md)). It writes the name at tid 1796, then the 23 bank settings `0xD18E`…`0xD1A4` at tids 1797–1819. Accepted bank-setting writes take 55–246 ms; three refusals take about 46 ms, while the Kelvin refusal (`0xD19C`, tid 1809) takes 5.283 ms. The name write takes about 232 ms. The live writes follow without a pause:

| tid | Write | Response | Since the previous command |
|--|--|--|--|
| 1819 | `0xD1A4 = 1` (the last bank setting) | OK, 85 ms | 74 ms |
| 1820 | `0xD1A5 = 9` | OK, 16 ms | 85 ms |
| 1821 | `0xD018 = 2` | OK, 15 ms | 17 ms |
| 1822 | `0xD007 = 100` | OK, 5 ms | 15 ms |
| 1823 | `0xD02E = 0` | OK, 4 ms | 5 ms |
| 1824 | `0xD001 = 0x0B` | OK, 15 ms | 4.5 ms |

The live writes continue at tids 1825–1842, every one OK in 4–18 ms: `0xD104` 0, `0xD031` 0, `0xD023` 3, `0xD029` 3, `0xD030` 3, `0xD189` 2, `0x5005` 4, `0xD017` 0, `0xD00B` 3, `0xD00C` −2, `0xD320` 10, `0xD321` 0, `0xD008` 0, `0x5015` −20, `0xD01C` `0x4000`, `0xD032` 0, `0xD34D` 1, `0xD00A` 1. At tid 1845, 1.7 s later, X RAW Studio reselects C1 and re-reads every bank; its bank reads (tids 1771–1794 and 1846 onwards) go `0xD18D`…`0xD1A4` and never touch `0xD1A5`.

Each live write carries the value just written to the bank property in the same position, in the bank write's own order (`0xD199`, `0xD19C`, `0xD19A`, `0xD19B` for the white balance group), which gives the 23-entry mirror in [the property reference](../docs/02-properties.md#live-shooting-properties): `0xD1A5` ← `0xD18E`, `0xD018` ← `0xD18F`, `0xD007` ← `0xD190`, `0xD02E` ← `0xD191`, `0xD001` ← `0xD192`, `0xD104` ← `0xD193`, `0xD031` ← `0xD194`, `0xD023` ← `0xD195`, `0xD029` ← `0xD196`, `0xD030` ← `0xD197`, `0xD189` ← `0xD198`, `0x5005` ← `0xD199`, `0xD017` ← `0xD19C`, `0xD00B` ← `0xD19A`, `0xD00C` ← `0xD19B`, `0xD320` ← `0xD19D`, `0xD321` ← `0xD19E`, `0xD008` ← `0xD19F`, `0x5015` ← `0xD1A0`, `0xD01C` ← `0xD1A1`, `0xD032` ← `0xD1A2`, `0xD34D` ← `0xD1A3`, `0xD00A` ← `0xD1A4`.

So `0xD1A5` is the first of the live writes, X RAW Studio's live twin of Image Size, not a 24th bank setting: it answers in 16 ms, within the live writes' 4–18 ms range, is never read with the bank, and carries `0xD18E`'s value. Accepted bank-setting writes are slower in this capture, but the fast Kelvin refusal shows that timing alone cannot classify a property. The camera accepted all four live writes whose bank twins it had refused (`0xD02E`, `0xD104`, `0xD031`, `0xD017`).

## What these captures cannot show

- Whether `0xD1A5` is addressed per bank: the selector was on C1 throughout.
- Whether the live write is optional. X RAW Studio's **Copy to CAMERA** dialog has a separate **CAMERA SETTING** checkbox for it [Published: fujifilm-ptp-recipes, static analysis]; both checkboxes were selected here, presumably.
- Cells 7 and 28, which never moved (`0` and `2` throughout; the author's **D RANGE PRIORITY** and **DIGITAL TELE-CONV.** were grayed **OFF** on screen), and cells 23 and 26, which stayed `0` on these color frames.
- Cell 29, which is `0` in all 20 X-T50 writes in the Preset Save editor walk and in the 26 writes in the maintainers' unpublished X-T50 captures. The separate public Profile_Read capture has an accepted X-T50 write with cell 29 = `1` (tid 379), as does the X-T30's first write (tid 44), so an all-zero tail isn't a rule.

## Capture notes

- The four inputs listed in [capture reproduction](reproduction.md) are pcapng, confirmed from their file headers and blocks; `ptpcap.py` detects the format from the file header.
- The X-T50 capture drops packets inside some JPEG downloads. The decoder loses the responses after a truncated transfer unless it abandons the pending reassembly at the next plausible container header; the profile writes and reads, being small, arrive whole.

The live mirror described here is the branch present in this captured combined save. X RAW Studio also offers separate **CAMERA SETTING** and **CAMERA CUSTOM SETTING** choices; for the optional branch, see [Live shooting properties](../docs/02-properties.md#live-shooting-properties). For recovery and metadata completeness, see [Reproducing the public capture analysis](reproduction.md).
