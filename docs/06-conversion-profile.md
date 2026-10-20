# 6. The `0xD185` conversion profile

`0xD185` is a single binary blob describing how the camera converts the RAF currently in its conversion buffer. In the observed runs it becomes readable after a native RAF upload; earlier reads answer `0x2002`. [Measured: X-T50] The post-upload profile reflects the RAF's as-shot settings, and it is what you patch to apply a recipe.

The following layout is checked against profiles identified as X-H1, X-Pro3, X-T30, GFX100S, and X-T50, plus libfuji's `xt5_*` files from an unconfirmed body consistent with an X100F. The identified set spans three processor generations and two sensor lines; the uncertain files aren't counted as another independently identified body. See [Profiles available](#profiles-available).

## Layout

```
offset  size  field
0x000   2     u16 LE  numParams
0x002   1     u8      IOPCode character count
0x003   …     UCS-2LE IOPCode, NUL-terminated, then zero padding up to 0x1FD
0x1FD   4×k   parameter table: k cells, each a 4-byte signed little-endian integer
```

The parameter table starts at byte `0x1FD` in the inspected profiles. Their table lengths vary. Bodies with fewer features have fewer cells, so Dynamic Range is at byte 533 and film simulation at 541 in every profile seen, read or written. That includes a GFX, so the layout isn't tied to a sensor line. [Published: libfuji captures] [Measured: X-T50] [Owner report: GFX100S] [Captured: X-T30 fw 2.01, FilmKit #13 capture]

Cell *i* is at `0x1FD + 4·i`. Because `0x1FD` is odd, every cell is unaligned. Reading a 32-bit value at a "round" offset such as 552 straddles neighboring cells and can produce plausible shifted values rather than a field.

### Lengths seen

| Body | Processor | Direction | Length | `numParams` | IOPCode | Source |
|--|--|--|--|--|--|--|
| X-H1 | X-Processor Pro | camera read | 601 | 23 | `FF129506` | [Published: libfuji `xh1_d185_sepia.txt`] |
| Unconfirmed; consistent with X100F | inferred X-Processor Pro | camera read | 601 | 23 | `FF129504` | [Published: libfuji `xt5_d185_initial.bin`; body inferred from the saved-profile code, provenance open] |
| X-Pro3 | X-Processor 4 | camera read | 621 | 28 | `FF159503` | [Published: libfuji `xpro3_d185_from_cam.bin`] |
| GFX100S | X-Processor 4 | camera read | 621 | 28 | `FF149502` | [Owner report: fw 2.13, 2026-09-17] |
| X-T30 | X-Processor 4 | camera read | 605 | 24 | `FF159502` | [Captured: X-T30 fw 2.01, FilmKit #13 capture] [Published: rawji] |
| X-T50 | X-Processor 5 | camera read | 625 | 29 | `FF189504` | [Measured: 2026-08-23] [Captured: fw 1.31, FilmKit #12 capture] |
| X-T5 | X-Processor 5 | camera read, implementation-derived shape | 625 (29 cells) | 29 | `FF179502` | [Published: fujicli, firmware unstated; no raw profile fixture supplied] |
| X-M5 | X-Processor 5 | camera read | 629 | | | [Published: FilmKit issue #18, fw 1.30] |
| X-Pro3 | — | host write | 629 | 29 | | [Published: libfuji `xpro3_d185_to_cam.bin`] |
| Unconfirmed; consistent with X100F | — | host write | 629 | 29 | | [Published: libfuji `xt5_d185_2.bin`; provenance open] |
| X-T30 | — | host write | 629 | 29 | | [Captured: X-T30 fw 2.01, FilmKit #13 capture] |
| X-T50 | — | host write | 629 | 29 | | [Captured: X RAW Studio, fw 1.31 and 1.32] |

### `numParams` means different things in each direction

- In a first camera read after an upload, `numParams` is the number of cells: `length − 4·numParams = 0x1FD` for 601/23, 605/24, 621/28, and 625/29. The X-M5's `numParams` isn't published.
- In a host write, X RAW Studio sends `numParams = 29` for a 30-cell (629-byte) blob, one less than the cell count. Deriving the table base from the tail of a host write therefore lands on `0x201`, one cell late.
- A camera read after a host write can echo the host's count. Two of libfuji's 23-cell reads are 601 bytes with `numParams = 29`, taken after X RAW Studio's write; libfuji's own comment says the camera keeps sending 601 bytes and echoes `0x1d`. [Published: libfuji `xh1_d185_xx.bin`, `xt5_d185_3_to_host`] On those bodies a tail-derived base lands at `0x1E5`, six cells (24 bytes) early: `0x1FD − 0x1E5 = 0x18`. The X-T50's 625/29 is the same both ways, so it can't show the effect.

So prefer the fixed base `0x1FD` and use the tail only as a check on a first read. The one-cell difference between the two numberings was noticed before: a fork of FilmKit ([macnow/filmkit](https://github.com/macnow/filmkit), April 2026) maps libfuji's index *N* to its own *N*+1, libfuji's header comments note a mismatch between `numParams` and the length, and a commenter in FilmKit issue #12 (September 2026) noted the 625-byte read against the 629-byte write. What this record adds is the cause: the host's `numParams` is one less than its cell count, and the camera addresses a fixed base, since 629-byte writes with `numParams = 29` would otherwise shift every field by a cell, and they don't.

### The IOPCode

A camera-specific identifier for the profile dialect. Record it from any unfamiliar body; no general processor-generation decoder is established here. The codes seen, from camera reads and from X RAW Studio's own saved-profile files: X-H1 `FF129506` and X100F `FF129504` (X-Processor Pro), X-T3 `FF159501`, X-T30 `FF159502`, X-Pro3 `FF159503`, and GFX100S `FF149502` (X-Processor 4), X-T5 `FA179502` or `FF179502`, X-H2 `FF179501`, and X-T50 `FF189504` (X-Processor 5). [Published: libfuji — captures and the X RAW Studio FP files in its tree] [Published: fujicli] [Published: fujifilm-ptp-recipes] [Measured: X-T50] [Owner report: GFX100S] The second hexadecimal byte varies within a processor generation: GFX100S `14` versus X-Pro3 `15`, and X-T5 `17` versus X-T50 `18`. The listed groups are disjoint across generations; they do not demonstrate a cross-generation collision or establish a rule for unfamiliar codes. The camera's `0xD184` property lists two such codes, `FF…` and `FA…`; see [the property reference](02-properties.md#bank-and-conversion-control). For the specific X-T50 counterexample to rawji's generation test, see [errata](errata.md#rawji).

libfuji's `xt5_*` files are consistent with an X100F; their origin is unconfirmed. Their IOPCode `FF129504` is the one X RAW Studio's own saved profile gives an X100F in libfuji's `fp/fp2`–`fp3`; X RAW Studio gives an X-T5 `FA179502` there, fujicli reads an X-T5 as `FF179502` with 29 cells, and a 23-cell profile lacks Clarity, Color Chrome FX Blue, and both toning cells, all of which an X-T5 has. Only the file names say X-T5. These contradictions make them unsuitable as identified X-T5 evidence, but a matching code doesn't establish the files' provenance. Confirmation from the original contributor remains open. [Published: libfuji] [Published: fujicli] [Inferred: X100F candidate]

## The host-write form

The inspected X RAW Studio host writes use the following 629-byte form. The evidence is the X-Pro3 pair, the X-T50's 20-write editor walk and separate Profile Read capture, the X-T30's 18-write Profile Read/editor subset, and 26 writes in the maintainers' unpublished X-T50 captures. [Published: libfuji captures — X-Pro3 621→629] [Captured: FilmKit #12 and #13; see capture reproduction] [Captured: X-T50 fw 1.32, maintainers' captures]

1. Take the profile as read, with your patches applied.
2. Extend a shorter profile to 629 bytes using an observed host-write template for that body and context where available; no universal fill rule is established. On the X-T50, cell 29 is `0` in all 20 editor-walk writes, but `1` in the separate Profile Read capture's first write (tid 379), which receives OK. On the X-T30, the first write after upload fills cells 24–29 with `0, 1, 0, 0, 2, 1`; later editor writes zero-extend. libfuji's X-H1 pair likewise has `1, 2, 1` in cells 25, 28, and 29. The X-Pro3 pair supports zero-extension in that case. [Captured: X-T50 fw 1.31 and X-T30 fw 2.01, FilmKit #12 and #13] [Published: libfuji `xh1_d185_initial.bin` → `xh1_d185_2.bin`; X-Pro3 pair] fujicli also [reports `0` or `1` in the X-T5's cell 29](https://github.com/karaolidis/fujicli/blob/10fdc2120ec25dc73fa94676e226d92f23f3db73/src/lib/devices/x_trans_v/x_t5/render.rs#L251-L252). Don't truncate a longer or unknown profile to this observed host form.
3. Set `numParams` to (number of cells) − 1, which is 29 for 629 bytes.
4. For the eight-character IOPCodes seen here, set the IOPCode length byte to `9`, counting the NUL, as the inspected host writes do.

Read-side IOPCode length bytes depend on the observed state. In the X-T50 Profile Read capture, tid 378 reads `8`, tid 379 writes `9`, and tid 408 reads back `9`; all three receive OK. The X-T30 likewise reads `8` initially and `9` after the host write. libfuji's 23-cell initial reads carry `8`, while `xt5_d185_3_to_host` carries `9`; its X-Pro3 read already carries `9`. These differences do not move the parameter table. [Captured: FilmKit #12 and #13] [Published: libfuji] The [reproduction guide](../captures/reproduction.md) identifies the public inputs and transactions.

Other accepted forms are reported. The [FilmKit #12 log](https://github.com/eggricesoy/filmkit/issues/12) explicitly records successful 625-byte writes and conversions on an X-T50 fw 1.31. A [fw 1.32 commenter](https://github.com/eggricesoy/filmkit/issues/12#issuecomment-5749574981) reports about 60 successful conversions but gives no write length. grawji preserves the native profile's length when patching it and reports conversion support on an X-E5, X-T3, X100F, and X-S20; these are source-reported successes, not captured byte lengths for each body. [Published: grawji]

rawji [constructs a 632-byte profile](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_profile.py#L165-L248), with header count `29` and 29 named parameters starting at `0x201`. At this chapter's `0x1FD` base, that is 30 complete cells plus three trailing padding bytes. It reports successful X-T30 conversion with tone controls using that form. Its earlier native-layout interpretation used a different, incorrect offset and its native parser remains a stub, so the report does not isolate length as the cause of unsuccessful tone edits or establish that this form is required. [Published: rawji]

Applying these steps to the X-Pro3's captured 621-byte read reproduces X RAW Studio's captured 629-byte write byte for byte.

## Parameter table

Indices follow FilmKit's numbering. rawji numbers the same cells one lower and measures them from `0x201`: rawji index *k* at `0x201` is the same byte as index *k*+1 here at `0x1FD`. fujicli and grawji count from `0x201` too. Either convention works on its own; mixing one project's indices with the other's base misreads every field.

Where a cell carries `[Captured: editor walk]`, X RAW Studio's editor was stepped through one setting at a time with a preview after each step, and only the cell or cells for that setting changed; see [the editor-walk transcript](../captures/x-rawstudio-editor-walk-xt50-xt30.md) (X-T50 fw 1.31 and X-T30 fw 2.01, FilmKit issues #12 and #13).

| Cell | rawji | Field | Encoding | Evidence |
|--|--|--|--|--|
| 0 | — | not characterized; `0` in every profile seen | | [Published: libfuji profiles] [Captured: FilmKit #12 and #13 captures] |
| 1 | 0 | Shooting Condition | `1` ON / `2` OFF in libfuji's numeric table; its saved-profile XML supplies the textual field name and `OFF` examples. `2` in every inspected capture profile. fujicli writes `0` to cells 0 and 1 with no failure reported | [Published: rawji — name] [Published: libfuji — [numeric definition](https://github.com/petabyt/libfuji/blob/a3bd237/fp/src/fp.h#L144-L147) and FP files] [Published: fujicli] |
| 2 | 1 | File type (output format) | `0x7` JPEG, `0x9` 8-bit TIFF, `0xB` 16-bit TIFF, `0x12` HEIF. On an X-T50, `11` gives a 16-bit TIFF of about 233 MB and only with `0xD183 = 1`; a body might ignore an unsupported format request and return a JPEG, so inspect the returned format | [Published: rawji] [Published: fujifilm-ptp-recipes, static analysis] [Published: FilmKit issue #15, X-T50] [Published: grawji — [fallback handling](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/controllers/exports.py#L215-L223)] |
| 3 | 2 | Image Size | `0xD18E`'s codes | [Published: rawji] [Published: fujicli] |
| 4 | 3 | Image Quality | `2` FINE, `3` NORMAL | [Captured: editor walk, both bodies] [Published: rawji] — FilmKit labels this Exposure Bias |
| 5 | 4 | Exposure Bias | EV × 1000, rounded (+⅔ EV is `667`, not `666`; −1 EV is `−1000`); the camera refuses off-by-one values for some ⅓-stop steps. The honored boundaries haven't been tested here: X RAW Studio's inspected capability entries read `M2P3` and rawji/grawji give −2…+3 EV, while fujicli and libfuji define ±3; grawji reports values below −2 rendering at 0 EV | [Published: rawji] [Captured: editor walk, X-T50] [Published: fujifilm-ptp-recipes, static analysis] [Published: fujicli] [Published: libfuji] [Published: grawji] |
| 6 | 5 | Dynamic Range | percentage: 100 / 200 / 400 in the tested non-HDR cases; no working Auto encoding established here. Shared with HDR, which can go up to 800 (and "HDR800+" = 800 with cell 7 = 3) | [Measured: X-T50] [Published: rawji — field identity only] [Published: FilmKit; libfuji and fujicli for HDR] [Captured: editor walk, X-T30 — 100→400] |
| 7 | 6 | D-Range Priority ("WideDRange") | unknown; see the cell 7 notes later in this section | |
| 8 | 7 | Film Simulation | same values as `0xD192` | [Measured: X-T50] [Published: FilmKit and rawji] [Captured: editor walk, X-T50 — 1→11] |
| 9 | 8 | Grain Effect | rawji reports `1` Off … `5` Strong Large, as `0xD195` writes, with values 6 and up ignored on an X-E5. The captured X-T50 conversion with a bank's recipe writes `7` for Off, matching the bank's read value; copying versus independent serialization remains unresolved. Profile value `1` as Off is untested here on the X-T50. Its editor walk writes `3`–`5`. See [Matching X RAW Studio](05-raw-conversion.md#matching-x-raw-studio) | [Captured] [Published: rawji, verified on an X-E5] [Captured: editor walk, X-T50 — 4→5→3] |
| 10 | 9 | Color Chrome Effect | 1 Off, 2 Weak, 3 Strong | [Measured: X-T50] [Captured: editor walk, X-T50 — 2→3] |
| 11 | 10 | White balance source | `1` = RAF's as-shot WB, `2` = use cell 12 | [Published: libfuji — the values] [Measured: X-T50] — FilmKit labels this Smooth Skin; rawji names it and writes `0` |
| 12 | 11 | White Balance mode | same nonzero modes as `0xD199`; `0` is a placeholder observed with cell 11 = `1` | [Published: libfuji; captures] [Measured: X-T50] [Captured: editor walk — `0x8008`→`4` on the X-T50, `0x8007`→`0x8008` on the X-T30] |
| 13 | 12 | WB shift, red | direct; ±9 in tested X-T50 cases. A tested out-of-range shift was ignored, not clamped | [Measured: X-T50] [Captured: editor walk, X-T50] |
| 14 | 13 | WB shift, blue | direct; ±9 in tested X-T50 cases. A tested out-of-range shift was ignored, not clamped | [Measured: X-T50] [Captured: editor walk, X-T50] |
| 15 | 14 | Color temperature | kelvin. The published older-body list has 31 presets; the capability table assigns the X-T50 2500–10000 in steps of 10, not yet tested here at a non-preset value (see the cell 15 notes later in this section) | [Published: X-Pro3 capture, 2200 K] [Published: rawji for the presets] [Published: fujifilm-ptp-recipes, static analysis] [Published: fujicli] |
| 16 | 15 | Highlight Tone | signed ×10 | [Measured: X-T50] [Captured: editor walk, X-T50 — 0→10] |
| 17 | 16 | Shadow Tone | signed ×10 | [Measured: X-T50] [Captured: editor walk, X-T50] |
| 18 | 17 | Color | signed ×10 | [Measured: X-T50] [Captured: editor walk, X-T50] |
| 19 | 18 | Sharpness | signed ×10 | [Measured: X-T50] [Captured: editor walk, X-T50 — −40→−20] |
| 20 | 19 | High ISO NR | same lookup as `0xD1A1` | [Measured: X-T50] [Captured: editor walk, X-T50 — `0x8000`→`0x4000`] |
| 21 | 20 | Lens Modulation Optimizer | `1` On, `2` Off, as `0xD1A3` (see the cell 21 and 22 notes later in this section) | [Captured: editor walk, both bodies, with the preview's MakerNote following] [Published: libfuji] [Published: fujicli] — rawji calls it reserved |
| 22 | 21 | Color Space | `1` sRGB, `2` Adobe RGB, as `0xD1A4` (see the cell 21 and 22 notes later in this section) | [Captured: editor walk, both bodies, with the preview's InteropIndex following] [Published: rawji] [Published: fujicli — values reversed, see errata] |
| 23 | 22 | Monochromatic Color, warm–cool | signed ×10, the value of `0xD193`, −180…+180 | [Captured: X-T50 fw 1.32, 2026-10-17] [Measured: X-T50 fw 1.32, 2026-10-17] [Published: libfuji, with the range] [Published: rawji, as `BlackImageTone`] |
| 24 | 23 | Smooth Skin Effect | 1 Off, 2 Weak, 3 Strong | [Published: rawji] [Captured] [Captured: editor walk, X-T50 — 3→2] |
| 25 | 24 | Color Chrome FX Blue | 1 Off, 2 Weak, 3 Strong | [Published: rawji] [Captured] [Captured: editor walk, X-T50 — 2→3] |
| 26 | 25 | Monochromatic Color, magenta–green | signed ×10, the value of `0xD194`, −180…+180 | [Captured: X-T50 fw 1.32, 2026-10-17] [Measured: X-T50 fw 1.32, 2026-10-17] [Published: libfuji, with the range] [Published: rawji, as `MonochromaticColorRG`] |
| 27 | 26 | Clarity | signed ×10 | [Published: rawji] [Captured] [Captured: editor walk, X-T50 — 30→0] |
| 28 | 27 | reserved; `2` in every X-T50 profile seen. fujicli names it Digital Tele-Converter, `1` on / `2` off (see the cell 28 notes later in this section) | | [Published: rawji — reserved] [Captured] [Published: fujicli — the name] |
| 29 | 28 | host-write cell absent from the inspected X-T50/X-T30 camera reads; meaning unresolved; X-M5 tail unknown | `0` in all 20 X-T50 editor-walk writes; `1` in the X-T50 Profile Read write (tid 379) and the X-T30's first write after upload | [Captured: FilmKit #12 and #13] [Published: fujicli — X-T5 `0`/`1`, historical source linked earlier] |

### Color temperature, cell 15

rawji reports these Kelvin presets for older bodies and a fallback to the coolest for unsupported values. Use the source's per-model capability distinction; this isn't a sweep of every older body here. [Published: rawji] [Published: fujifilm-ptp-recipes, static analysis — the 31-value list is the older `Std1` type]

```
2500 2550 2650 2700 2800 2850 2950 3000 3100 3200 3300 3400 3600 3700 3800 4000
4200 4300 4500 4800 5000 5300 5600 5900 6300 6700 7100 7700 8300 9100 10000
```

Newer-body support for 2500–10000 in steps of 10 is published capability evidence. X RAW Studio's conversion capability table gives that range to the listed X-series bodies from the X-Pro3 onward, including the X100V, X-T4, and X-T50 [Published: fujifilm-ptp-recipes, static analysis]. rawji and grawji describe free Kelvin on X-Processor 5 bodies; since September 2026 grawji also enables it for X-Pro3-era bodies. Those reports share observation lineage and do not independently establish the 10 K grid. [Published: rawji] [Published: grawji] fujicli uses 10 K granularity without snapping to the older preset list on its X-T5 [Published: fujicli]. No conversion here has been developed at a non-preset value, so for the X-T50 this is Published only; see [open questions](open-questions.md#raw-conversion).

### Table length

The X-H1 and unconfirmed `xt5_*` 601-byte reads stop after cell 22 (Color Space); the X-T30's 24 cells stop after cell 23. A parser must check bounds per cell, not assume every cell exists. The X-M5's reported 629-byte read would have room for 30 cells at this base, but its bytes and count are unavailable here; whether its tail is cell 29 remains open.

### Dynamic range, cell 6

The X-T50 tests accepted and stored `100`, `200`, `400`, and `-1`; acceptance alone doesn't establish rendered behavior. The `-1` output is tagged Manual with `DevelopmentDynamicRange = 100` and no `AutoDynamicRange`, matching the DR100 control's Fujifilm tags. Its sampled mean absolute pixel difference from that control was 0.43, the closest comparison reported; it wasn't pixel-identical, and no second DR100 control established the noise floor. A tested value above the RAF's as-shot DR rendered green. HDR values and broader acceptance remain separate questions. See [RAW conversion](05-raw-conversion.md#dynamic-range). [Measured: X-T50 fw 1.32, 2026-09-07; MakerNotes re-read 2026-10-17] rawji writes `1`, `2`, or `3` here, although this record hasn't tested what those values render; they aren't the established percentage encoding; see [errata](errata.md#rawji).

### Lens Modulation Optimizer, cell 21, and Color Space, cell 22

Both carry the bank encoding of `0xD1A3` and `0xD1A4`. In the FilmKit #12 editor walk, one write changed only cell 21, `2`→`1`, and the camera's preview went from `LensModulationOptimizer` Off to On in its MakerNote; the next changed only cell 22, `2`→`1`, and the preview's `InteropIndex` went from R03 (Adobe RGB) to R98 (sRGB). The X-T30 walk in #13 repeats both in the other direction. Across every X RAW Studio preview decoded here, cell 21 and the MakerNote never disagree: on the X-T50, 19 previews written with `1` carry LMO On and 27 written with `2` carry Off (3 and 17 of them in the public editor walk); on the X-T30, 15 and 3. The MakerNotes come from complete APP1 segments; the captured pixels are incomplete. [Captured: X-T50 fw 1.31 and 1.32; X-T30 fw 2.01]

A frame shot with LMO On reads `1` in its as-shot profile (DSCF4072, 2026-09-07; DSCF0362, 2026-06-24), and frames shot with it Off read `2` (the 2026-10-17 toning captures). [Captured: X-T50 fw 1.32] Whether X RAW Studio copies `0xD1A3` into cell 21 when converting with a bank's recipe, or keeps the as-shot value, the 2026-09-07 capture can't show: C6 held `1` and the frame was shot with `1`.

### Monochromatic Color, cells 23 and 26

Cell 23 is warm–cool and cell 26 is magenta–green. Each takes its bank property's value unchanged: signed ×10, the menu's sign, positive warm–cool warm and positive magenta–green green. X RAW Studio sent a warm–cool +7 as `70` in cell 23 and a magenta–green −4 as `−40` in cell 26, and the JPEGs it got back carried +7 and −4 in their MakerNotes and rendered warm and magenta. [Captured: X-T50 fw 1.32, 2026-10-17] [Measured: X-T50 fw 1.32, 2026-10-17, on the saved output files] See [X RAW Studio converting with Monochromatic Color](../captures/x-rawstudio-toning-xt50.md).

- The tested endpoint values reach the render. Conversions with `180` in cell 23, and with `−180` in cell 26, carry WC +18 and MG −18 in their MakerNotes and render a strong warm and a strong magenta tint. [Measured: X-T50 fw 1.32, 2026-10-17] libfuji gives both cells a range of −180…+180. [Published: libfuji] The captured conversions show the same scale at `70` → +7 and `−40` → −4. [Captured: X-T50 fw 1.32, 2026-10-17]
- In the tested case the conversion took its toning from these cells and not from the active bank: with the body's active bank at WC +18 / MG −18, one frame converted with both cells at `0` carried neutral MakerNotes and rendered neutral. [Measured: X-T50 fw 1.32, 2026-10-17] These captures can't show how an upload seeds the cells; see the transcript.
- A warm–cool value written to cell 26 renders green. Conversions with `180` and `90` in cell 26 carry MG +18 and MG +9 in their MakerNotes and render a strong and a weaker green. [Measured: X-T50 fw 1.32, 2026-10-17]
- On color frames, the cells might hold something else. libfuji reports white-balance-dependent 32-bit words there on color simulations, reset to `0` when a shift is set, and X RAW Studio's own saved profile of a Nostalgic Neg. frame holds `−1` in both fields. [Published: libfuji — comments and the X-T5 FP file] The two X-T50 color frames decoded here (Classic Chrome/Daylight; PROVIA/Auto) read `0` in both cells, as shot and in every X RAW Studio write. [Captured: X-T50 fw 1.32] More frames under more white balance modes would settle it; see [open questions](open-questions.md#raw-conversion).
- Read-side cell availability follows the inspected profile's length; a longer host write does not establish that the body implements every appended cell. The X-H1 and unconfirmed `xt5_*` reads stop before cell 23. The X-T30's 605-byte read ends at cell 23, which fits a body with the warm–cool axis alone. [Captured: X-T30 fw 2.01]

### D-Range Priority, cell 7 — unknown

Three published tables, two of them in disagreement, and no render evidence:

| Source | Off | Weak | Strong | Other |
|--|--|--|--|--|
| libfuji `fp/src/fp.h` | 0 | 1 | 2 | 3 = HDR800+ |
| fujicli (as `0xD191`) | 0 | 1 | 2 | `0x8000` Auto; 3 = Plus, with cell 6 = 800 for HDR800+, from X RAW Studio captures |
| FilmKit (flagged speculative in its code) | 0 | 2 | 3 | 1 = Auto |

X RAW Studio's own D-Range Priority label map runs 0–3, and its bank builder copies the same field verbatim to `0xD191`. [Published: fujifilm-ptp-recipes, static analysis] The one non-zero data point is libfuji's X-H1 Sepia profile, a DR200 frame with cell 7 = `1`; libfuji also notes that a non-zero cell 7 keeps the frame's DR and zeroes both tones. That comment is not demonstrated by the profile bytes, whose tone cells are both `−10`. [Published: libfuji] The bank property `0xD191` (Off 0, Weak 1, Strong 2, Auto `0x8000`) isn't evidence for cell 7 on its own: `0xD190` has an Auto value, and that value didn't render Auto through cell 6 in the X-T50 test, so the bank and profile encodings are known to differ for the very same setting. Every X-T50 profile seen holds `0`. To settle cell 7, upload frames shot at **DR AUTO** and at **D RANGE PRIORITY** Weak, Strong, and Auto and read cells 6 and 7 as shot, then write each candidate and inspect the output's priority tags. In [ExifTool's definitions](https://github.com/exiftool/exiftool/blob/2200871/lib/Image/ExifTool/FujiFilm.pm#L842-L859), `DRangePriority` (`0x1443`) selects Auto or Fixed; `DRangePriorityAuto` (`0x1444`) maps `1` Weak, `2` Strong, and `3` Plus; `DRangePriorityFixed` (`0x1445`) defines only `1` Weak and `2` Strong. These metadata values are not by themselves cell-7 encodings. Until then, don't write it.

### Digital Tele-Converter, cell 28 — a candidate

fujicli names cell 28 Digital Tele-Converter, `1` on / `2` off, and says the camera can't turn it on for a frame shot without it. X RAW Studio's saved profiles also carry a `DigitalTeleConv` field, which corroborates the feature's presence but does not uniquely assign it to a binary cell; the cell-28 mapping comes from fujicli. [Published: fujicli] [Published: libfuji — the FP files] The X-T50 holds `2` in every profile seen, consistent with the candidate's Off encoding, but that constant value does not settle the identity. [Inferred] A develop with cell 28 = `1` on a frame shot with the tele-converter on, checked against the output's dimensions and `CropMode` (ExifTool `0x104D`), would settle it; see [open questions](open-questions.md#raw-conversion).

## Bank properties and profile cells

In the captured X-T50 conversion with a bank's recipe, seventeen profile-cell values matched the corresponding bank reads. This establishes the listed value pairs in that run, not an unconditional copying rule for every setting or body. [Captured: X-T50 fw 1.32, 2026-09-07]

| Bank | Cell | | Bank | Cell | | Bank | Cell |
|--|--|--|--|--|--|--|--|
| `0xD190` | 6 | | `0xD19A` | 13 | | `0xD1A0` | 19 |
| `0xD192` | 8 | | `0xD19B` | 14 | | `0xD1A1` | 20 |
| `0xD195` | 9 | | `0xD19C` | 15 | | `0xD1A2` | 27 |
| `0xD196` | 10 | | `0xD19D` | 16 | | `0xD1A4` | 22 |
| `0xD199` | 12 | | `0xD19E` | 17 | | `0xD197` | 25 |
| | | | `0xD19F` | 18 | | `0xD198` | 24 |

The two Monochromatic Color properties follow the same rule: `0xD193` into cell 23 and `0xD194` into cell 26. That was seen in X RAW Studio's own editor rather than in a bank copy, with the bank encoding unchanged. [Captured: X-T50 fw 1.32, 2026-10-17] `0xD1A3` presumably goes into cell 21 the same way; the one capture that could show it had both at `1`. [Inferred]

Cell 11 has no bank counterpart. To make the converter use the white balance in cell 12, set it to `2`; to keep the RAF's own, leave it at `1`. libfuji explicitly calls cell 12's `0` a [dummy as-shot value controlled by the separate shooting-conditions field](https://github.com/petabyt/libfuji/blob/a3bd237/fp/src/fp.h#L177-L196). The observed pair `(cell 11, cell 12) = (1, 0)` does not establish that cell 12 = `0` independently selects as-shot white balance or has a bank counterpart. Two sources differ in their handling of shifts in cells 13 and 14 under as-shot white balance: fujicli treats them as inert and writes `0`; grawji writes them, and its [transplanted Auto-WB explanation](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/transplant/embed.py#L18-L31) says the engine adds them to the RAF's stored levels. [Published: fujicli] [Published: grawji] General applicability across as-shot modes and bodies remains untested here.

## Parsing safely

Because a misaligned read produces plausible-looking numbers, validate a profile before writing to it. The following is a conservative heuristic for the inspected non-HDR profiles, not a general validator for all valid profiles (the published HDR800 candidate would fail it):

1. Try base `0x1FD` first. As fallbacks, try the tail-derived base (`length − 4·numParams`) and one cell either side of it, remembering that a read after a host write can carry the host's `numParams`.
2. Accept a base only if both of these hold: cell 6 is exactly 100, 200, or 400, and cell 8 is a known film simulation. These narrow sets reduce accidental alignment matches; they don't prove a layout, so preserve ambiguous inputs without writing.
3. Break ties with the one-indexed effect cells (10, 24, 25 in the range 1–3). Don't use cell 11; its domain is 1–2, which almost anything satisfies.
4. If no base passes, don't write.

On every profile seen, `0x1FD` passes with the highest score. On the GFX100S's first profile it scored 5; `0x201` scored 3 and `0x1F9` scored 2. [Owner report: GFX100S]

## Profiles available

| Profile | Where |
|--|--|
| X-H1, X-Pro3, and an unconfirmed body consistent with X100F (`xt5_*`) — camera reads and host writes | [petabyt/libfuji](https://github.com/petabyt/libfuji) `fp/d185/` (MIT) |
| X-T50 fw 1.31 and X-T30 fw 2.01 — camera reads and X RAW Studio writes, inside USB captures | [FilmKit issues #12 and #13](../captures/README.md#public-captures) (public attachments) |
| X-T50 fw 1.32 — camera read (625 B) and X RAW Studio write (629 B) | Maintainers' captures, not published; see [captures](../captures/README.md) |
| GFX100S — camera read (621 B), header and first 64 bytes | Owner report; see [captures](../captures/README.md) |
