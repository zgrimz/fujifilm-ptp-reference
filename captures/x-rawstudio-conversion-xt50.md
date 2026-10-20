# X RAW Studio converting a RAF — X-T50

Source: a Wireshark/USBPcap capture that the maintainers made on September 7, 2026. Fujifilm X RAW Studio on Windows, connected to an X-T50 on firmware 1.32: open `DSCF4072.RAF` (shot by that body at DR400), choose the camera's C6 bank as the recipe, convert. The raw capture contains the photo and isn't published; this page is the decoded command stream.

## Sequence

```
SendObjectInfo 0x900C  (as FUP_FILE.dat)
SendObject2    0x900D  (the RAF, ~87 MB)
GetDevicePropValue 0xD185   → 625 bytes, the as-shot profile
SetDevicePropValue 0xD185   ← 629 bytes, the host-write form
SetDevicePropValue 0xD183
poll GetDevicePropValue 0xD212 (event list) until it reports 0xD20E
GetObjectHandles
GetObjectInfo ×3
GetObject
DeleteObject
```

## What it shows

- It converts three times for one job: an as-shot preview when the file is opened (`0xD183 = 0`, ~1.1 MB JPEG), a recipe preview when the bank is chosen (`0`), then the final conversion (`1`, ~6.5 MB).
- X RAW Studio polls `0xD212`, the camera's event list, during conversion: `0000` (zero events) while waiting; when it proceeds to retrieve the JPEG, 8 bytes `0100 0ED2 …`, one event for property `0xD20E` (libgphoto2 calls it FreeSDRAMImages) with a u32 event value. The separate public editor-walk capture also reports this event after deletion, so event presence alone is not a unique conversion-completion signal. Interpret it with the triggering operation and a validated output baseline; see [completion](../docs/05-raw-conversion.md#completion).
- It re-reads `0xD185` after every conversion, and the shared cells 0–28 equal the preceding write. The 625-byte read has no cell 29; it is not byte-identical to the 629-byte write.
- Seventeen bank/profile pairs have matching raw values. These pairs match the read of C6 in this capture. Equality supports the mapping but doesn't establish unconditional copying or behavior under other settings: `D190→6 D192→8 D195→9 D196→10 D199→12 D19A→13 D19B→14 D19C→15 D19D→16 D19E→17 D19F→18 D1A0→19 D1A1→20 D1A2→27 D1A4→22 D197→25 D198→24`.
- This capture includes a DR400-to-DR200 conversion. The frame was shot at DR400; X RAW Studio wrote 200 and the returned metadata reports `DevelopmentDynamicRange: 200`. The captured DR writes are 100, 200, or 400. This doesn't establish every allowed DR transition or pixel equivalence.
- X RAW Studio writes Grain Off as `7`, the bank's read-side value.
- Cell 15 held 10000, matching the bank's Kelvin value while white balance was Auto. This establishes matching values, not how X RAW Studio produced them; the value's effect on an Auto conversion is untested.
- Cell 21 reads `1` in the as-shot profile and in every write and read-back. DSCF4072 was shot with Lens Modulation Optimizer On, and the three JPEGs X RAW Studio got back carry `LensModulationOptimizer` On. C6's `0xD1A3` read `1` too, as every bank's did, so this capture can't tell copying `0xD1A3` into cell 21 from keeping the as-shot value. Cells 7, 23, 26, and 28 read `0`, `0`, `0`, and `2` throughout; cell 29 is `0` in every write.

## Capture notes

USBPcap dropped packets during the 87 MB upload. A decoder that reassembles split containers per direction can lose later OUT commands behind the truncated `SendObject2`. This transcript comes from an unpublished scratch decoder that recovered the command stream by detecting later plausible container starts; [`tools/ptpcap.py`](../tools/README.md) offers an explicit, heuristic recovery mode with incomplete-transfer reporting, described in [Reproducing the public capture analysis](reproduction.md). This private input hasn't been reproduced through that shipped path. The small transfers (the 625/629-byte profiles) arrived intact in the scratch decoder's output. The downloaded JPEG didn't: its EXIF survived, but its pixel data has holes, so metadata isn't pixel validation.
