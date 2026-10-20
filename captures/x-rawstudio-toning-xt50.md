# X RAW Studio converting with Monochromatic Color — X-T50

Source: three USBPcap captures that the maintainers made. Fujifilm X RAW Studio on Windows, connected to an X-T50 on firmware 1.32, converting `DSCF1078.RAF` under ACROS. That body shot the RAF in Velvia at DR400, so it carries no toning of its own. The RAF was already in the camera when each capture started, so the captures contain no upload. Decoded with [`tools/ptpcap.py`](../tools/README.md), and the profile writes were read cell by cell from the 641-byte data containers. The raw captures contain the photo and aren't published.

| Capture | Body's active bank | X RAW Studio's toning | JPEG MakerNote (`BWAdjustment` / `BWMagentaGreen`) | Rendered tint, CIELAB a\* / b\* of the mid-tones |
|--|--|--|--|--|
| 1 | C7, toning 0 / 0 | WC +7, MG 0 | +7 / 0 | +2 / +10, warm |
| 2 | C7, toning 0 / 0 | WC 0, MG −4 | 0 / −4 | +5 / −3, magenta |
| 3 | C6, toning WC +18 / MG −18 | WC 0, MG 0 | 0 / 0 | 0.0 / 0.0, neutral |

The profile cells and the JPEG MakerNotes are capture evidence. The tints and CIELAB values were measured on the complete 7728×5152 JPEGs X RAW Studio saved to disk, not on the captures, whose JPEG downloads are truncated. [Measured: X-T50 fw 1.32, 2026-10-17]

## Sequence

Each preview and the final conversion is the flow in [X RAW Studio converting a RAF](x-rawstudio-conversion-xt50.md), with no upload:

```
SetDevicePropValue 0xD185   ← 629 bytes, the host-write form
SetDevicePropValue 0xD183   0 for a preview, 1 for the final conversion
poll GetDevicePropValue 0xD212 until it reports 0xD20E
GetObjectHandles, GetObjectInfo ×3, GetObject, DeleteObject
GetDevicePropValue 0xD185   → 625 bytes, shared cells match the preceding write
```

The 625-byte read-back is not byte-identical to the 629-byte write; the earlier comparison is of their shared cells 0–28. Between conversions X RAW Studio polls `0xD36A` and `0xD36B`, the battery properties, every 3 seconds. In these sequences it requests toning changes through the profile and writes no bank property, selector, or live property.

## The cells

Across the shared cells in the complete profile writes and read-backs, the only changing values in these three captures are:

| Cell | Capture 1 | Capture 2 | Capture 3 |
|--|--|--|--|
| 8, film simulation | `13` (ACROS + Ye) in the first write, `12` (ACROS) after | `12` | `12` |
| 23 | `0`, then `60`, then `70` as the slider reached +7 | `0` | `0` |
| 26 | `0` | `0`, then `−40` | `0` |

The profile values and JPEG MakerNotes identify cell 23 as warm–cool and cell 26 as magenta–green, each carrying its bank property's value unchanged (signed ×10). The rendered JPEGs agree in direction with the menu's polarity: positive WC is warm, negative MG is magenta. [Measured: X-T50 fw 1.32, 2026-10-17]

Capture 3 answers a second question for this frame and bank state. With the body's active bank at WC +18 / MG −18, a conversion with both cells at `0` carries neutral toning MakerNotes and renders neutral (a\* 0.0, b\* 0.0), so this conversion took its toning from the profile, not from the active bank. [Measured: X-T50 fw 1.32, 2026-10-17] These captures can't show whether the camera seeds cells 23 and 26 from the active bank in the profile it returns after an upload; cell 26 of this frame's after-upload profile read `0` the same day with the same bank active.

## Other cells

The other shared cells hold the same values in every write, read-back, and capture:

- Cell 18 (Color) is `0`, although this frame's own profile, read after an upload the same day, holds `30` (Velvia shot at Color +3).
- Cell 21 (Lens Modulation Optimizer) is `2`, Off, matching the frame's MakerNote; cell 28 (reserved; fujicli names it Digital Tele-Converter) is `2`.
- Cell 29 is present only in the host writes and is `0` in these three captures. This is not universal for the X-T50: the public FilmKit #12 Profile capture's first write has `1`; see [capture reproduction](reproduction.md).

The others are the frame's as-shot values: DR400 in cell 6, as-shot white balance in cells 11–15, Highlight −1.5, Shadow −1, and Sharpness −1 in cells 16, 17, and 19.

## Capture notes

- USBPcap wrote these as pcap, not pcapng, despite the `.pcapng` name; `ptpcap.py` reads both.
- Each conversion's `GetObjectInfo`, which X RAW Studio requests three times before downloading, is a complete 114-byte dataset: StorageID `0x10000001`, ObjectFormat `0x3801`, ProtectionStatus `0`, and a `DSCF000n.jpg` filename. Its ObjectCompressedSize equals the declared length of the `GetObject` data phase and, for each final conversion, the saved JPEG's size: 26,835,053, 26,625,646, and 26,446,458 bytes. [Captured: X-T50 fw 1.32, 2026-10-17] [Measured: X-T50 fw 1.32, 2026-10-17, saved files]
- The 65,535-byte snapshot length truncates each JPEG download. The decoder loses the responses after it, but the commands still decode. The profiles are small and arrive whole; the earlier pixel measurements come from the saved output files, not from the captured downloads.
