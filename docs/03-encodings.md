# 3. Value encodings

How each of the 23 bank settings is encoded on the wire, and how `0xD1A5` and the bank name behave. The captures and tests here use a 2-byte little-endian field for integer bank settings in the data phase of `GetDevicePropValue` / `SetDevicePropValue`. Filmcase reports X-S10 bank-push readback behavior through a 4-byte integer write path, while its historical sweep used 2-byte writes [Published: Filmcase]. The 4-byte width comes from the implementation accompanying its [push/readback fixes](https://github.com/gosku/Filmcase/commit/5652d21a45a244fc18f35e8441fe83b1be6a8931), not a capture; see [the X-S10 evidence](07-cameras.md#x-s10). This isn't a complete acceptance matrix, and 4-byte behavior is untested on the X-T50.

## Read signed or unsigned?

Fujifilm uses the high bit (`0x8000`) to mark special values, so you must read some properties unsigned:

| Read unsigned | Read signed |
|--|--|
| White Balance mode, High ISO NR, D-Range Priority, Kelvin, Film Simulation, effect strengths | Tones, Color, Sharpness, Clarity, WB shifts, Monochromatic Color, Dynamic Range (for its `-1` Auto value) |

Reading Auto White Priority (`0x8020`) as signed gives −32736, and D-Range Priority Auto (`0x8000`) gives −32768. Neither matches any table. The reverse mistake is as common: a GFX100RF took Sharpness `−20` and read it back as `65516` to a decoder that treated the property as unsigned. [Published: GFX100RF, fuji-ptp-notes] Both peer records read the same nine properties signed and Dynamic Range unsigned, but they disagree about DR Auto: fuji-ptp-notes lists `65535`, while fujifilm-ptp-recipes' [bank table](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/properties.md#L77-L111) gives `0` and interprets `65535` under active D-Range Priority as a placeholder. This record displays `0xFFFF` as signed `−1`; its meaning depends on the body and state evidence discussed under [Dynamic Range](#0xd190-dynamic-range). [Published: fujifilm-ptp-recipes] [Published: fuji-ptp-notes]

Ranges, as the camera's menus bound them: Highlight and Shadow Tone −2…+4 in whole or half steps depending on the body and firmware (see the tone section later in this chapter), Color and Sharpness −4…+4, Clarity −5…+5, white balance shift −9…+9. [Published: fujifilm-ptp-recipes] [Published: fujicli] Monochromatic Color's range is per body, as described later in this chapter. Only the Monochromatic Color grid has been probed by writing off-grid values (described later); a commenter in FilmKit issue #12 reports tones of ±4.0 accepted on an X-T50 at fw 1.32, which would exceed the menu's −2 [Community], so the tone floor is an [open question](open-questions.md#bank-protocol).

## Observed bank-value behaviors

- Accepted and matched. The camera answers OK and the value reads back as written.
- Refused with `0x201C`. In the reported state-gated tests, the value remains unchanged. The code alone does not establish the final value or distinguish a state gate from an invalid encoding; see [Why a write is refused](04-custom-slots.md#why-a-write-is-refused).
- Accepted and normalized. The camera answers OK and stores a different value with the same meaning. Grain Effect is the known case.

Only a write followed by a read-back tells these apart. Keep the command response and read-back result separate: an OK response alone doesn't establish a match, and a missing response leaves the command outcome unknown. These three observed behaviors aren't an exhaustive command-outcome model; see [command outcomes and verification](11-client-implementation.md#report-command-outcomes-and-state-verification-independently). Don't assume a value outside a property's accepted set can only be refused; a client must also detect an ignored or normalized write.

---

## `0xD18E` Image Size

| Value | Meaning | Evidence |
|--|--|--|
| `1` | S 3:2 | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `4` | M 3:2 | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `7` | L 3:2 | [Published: FilmKit] [Captured] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `8` | L 16:9 | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `9` | L 1:1 | [Captured: X RAW Studio author's screen] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `14` | L 4:3 — held by all six GFX100S banks, and 4:3 is the GFX sensor's native ratio | [Owner report: GFX100S fw 2.13, USB diagnostics, for the value] [Published: fujifilm-ptp-recipes, static analysis for the meaning] |
| `16` | L 5:4 — read from the bank a GFX100S was parked on, without a select | [Owner report: GFX100S fw 1.32, USB diagnostics, for the value] [Published: fujifilm-ptp-recipes, static analysis for the meaning] |

fujifilm-ptp-recipes' static analysis of X RAW Studio finds that the value is a composite of size × aspect ratio: a 27-entry table covers L, M, and S against nine ratios (3:4, 1:1, 7:6, 5:4, 4:3, 3:2, 16:9, 65:24, 17:6). The application carries a fallback for bodies that refuse the composite: on the bank path it sends only the size to `0xD1A8`, dropping the ratio; on the live path it sends both parts through `0xD03A`/`0xD03B`. Which bodies refuse the composite is the source's guess, not a table entry, and its guess includes X-Trans V bodies (X-H2S, X-S20, X-M5); no body has been seen to trigger the fallback. Five of the values in the preceding table were set by hand on an X-T50 and read back as the table predicts, which confirms the decode; the two GFX values rest on it. [Published: fujifilm-ptp-recipes, static analysis] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] The full table is in that project's `docs/reverse-engineering/xrfc-value-tables.md`.

The codes the X-T50 hasn't been swept for, from the same table and from fujicli's schema for a 40 MP body, are `2` S 16:9, `3` S 1:1, `5` M 16:9, `6` M 1:1, `10` S 4:3, `12` S 5:4, `14` L 4:3, `16` L 5:4, `18` M 4:3, and `20` M 5:4. The capability table assigns the X-T50 `1`–`10`, `12`, `14`, `16`, `18`, and `20`. It assigns the X-T30 III a different set: `1`–`9` plus `28`–`30` for its INSTAX sizes, without the X-T50's extra 4:3 and 5:4 codes. See the [per-body size variants](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xrfc-value-tables.md#L283-L305). [Published: fujifilm-ptp-recipes, static analysis] [Published: fujicli] The conversion profile's cell 3 uses the same codes. [Published: rawji] [Published: fujicli]

Each body offers its own subset of sizes and ratios. Treat this as a setting to carry through, not to author.

## `0xD18F` Image Quality

| Value | Meaning | Evidence |
|--|--|--|
| `1` | RAW only | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `2` | FINE | [Captured] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `3` | NORMAL | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `4` | FINE + RAW | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |
| `5` | NORMAL + RAW | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] |

A GFX100S holds `2` in every bank. [Owner report] X RAW Studio's capability table lists `2` and `3` for X-series bodies and `6`, `2`, and `3` for GFX, where `6` is SUPER FINE in its label table, and the application remaps `2`→`4`, `3`→`5`, and `6`→`7` before the wire under a condition its analysis hasn't identified. [Published: fujifilm-ptp-recipes, static analysis] Given the X-T50's `4` and `5`, that remap adds RAW. [Inferred] X RAW Studio's label map also carries `20`–`23` for HEIF quality variants, which no capability set lists. [Published: fujifilm-ptp-recipes, static analysis] The conversion profile's cell 4 holds `2` for FINE and `3` for NORMAL. [Captured: X-T50 fw 1.31 and X-T30 fw 2.01, FilmKit #12 and #13 captures]

## `0xD190` Dynamic Range

| Value | Meaning | Evidence |
|--|--|--|
| `100`, `200`, `400` | DR100, DR200, DR400 — the percentage itself | [Published: FilmKit] [Measured: X-T50] |
| `0xFFFF` (−1) | DR Auto | [Measured: X-T50 fw 1.32, 2026-09-07] [Owner report: GFX100S fw 2.13, menu-confirmed] [Published: X-S10, Filmcase — read from a bank, then written and read back; firmware unstated] [Community: X-T30 II fw 2.04, a report in fujifilm-ptp-recipes' unmerged pull request #2 — `65535` with the priority Off, and accepted as a write] |
| `0` | refused `0x201C`, with `0xFFFF` and `100` accepted on the same bank moments apart | [Measured: X-T50 fw 1.32, 2026-10-15] |

Several sources use 1/2/3 for DR100/200/400. Those are UI enumerations, not the wire encoding. No working Auto encoding is established for the conversion profile here (see [the conversion profile](06-conversion-profile.md#dynamic-range-cell-6)).

The reading of Auto is disputed. fujifilm-ptp-recipes gives `0` for DR Auto and interprets an X-H2's `0xFFFF` while D-Range Priority is active as a placeholder. Its bank-property account reports an Auto/Off pair confirming the write interlock and says `0xD190` reads the true value with priority Off, without giving that numeric baseline. Its separate live-property account explicitly reports both the interlock and the `65535` behavior as confirmed by an Auto/Off pair. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] Two bodies here hold `0xFFFF` for a bank whose menu says **AUTO**, both menu-confirmed; an X-S10's bank read it [Published: X-S10, Filmcase], and an X-T30 II is reported to hold it with the priority Off. fuji-ptp-notes lists the same value without marking its value table as measured or identifying a source for that entry; Filmcase separately supplies the X-S10 evidence. An X-T50 refuses `0` as a write, and a bank holding DR100 keeps reading `100` after D-Range Priority is set to Strong in the menu (`0xD191` moved `0`→`2`, nothing else changed), so `0xFFFF` is a stored DR Auto value on that X-T50. [Measured: X-T50 fw 1.32, 2026-10-15] That X-T50 result doesn't disprove the X-H2 report. A numeric bank read-back comparison with a known non-Auto DR baseline would distinguish the X-H2 bank interpretations. See [errata](errata.md#fujifilm-ptp-recipes).

Writes of DR200 and DR400 depend on the bank's ISO. See [ISO gating](04-custom-slots.md#iso-gating).

## `0xD191` D-Range Priority

| Value | Meaning |
|--|--|
| `0x0000` | Off |
| `0x0001` | Weak |
| `0x0002` | Strong |
| `0x8000` | Auto |

[Measured: X-T50 fw 1.32, 2026-09-17]: bank C1 was read four times, changing only the camera's **D RANGE PRIORITY** menu item between reads. Every other property came back byte-identical each time. [Owner report: GFX100S fw 2.13]: a bank set to **AUTO** in the menu reads `0x8000`, and Strong (`2`) written over USB reads back. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]: the same four values, each written and read back. [Published: X-S10, Filmcase — each of the four reported written, read back, and visually checked on the body; firmware unstated]: the same four values on an X-Trans IV body, which fuji-ptp-notes relays. [Published: fujicli]: the same four values on an X-T5 and an X-S20. Four bodies with raw bytes agree, across X-Processor 4 and 5, the X-S10 the first X-Trans IV among them. No older body has reported. Which bodies' menus have **D RANGE PRIORITY** is in [effect controls in the menus](07-cameras.md#effect-controls-in-the-menus). [Published: Fujifilm manuals]

The cited static analysis describes X RAW Studio as never sending Auto, reasoning that a converter works on a frame whose dynamic range was already decided at capture. [Published: fujifilm-ptp-recipes, static analysis] No working Auto encoding is established for the conversion profile here; [D-Range Priority in cell 7](06-conversion-profile.md#d-range-priority-cell-7--unknown) remains unresolved.

Auto is a high-bit value, not an in-sequence 3, so read it unsigned. With the priority on, the camera controls Dynamic Range and both tone curves itself — see [the interlock](04-custom-slots.md#the-d-range-priority-interlock).

## `0xD192` Film Simulation

| Value | Film simulation | | Value | Film simulation |
|--|--|--|--|--|
| `0x01` | PROVIA / Standard | | `0x0B` | Classic Chrome |
| `0x02` | Velvia / Vivid | | `0x0C` | ACROS |
| `0x03` | ASTIA / Soft | | `0x0D` | ACROS + Ye |
| `0x04` | PRO Neg. Hi | | `0x0E` | ACROS + R |
| `0x05` | PRO Neg. Std | | `0x0F` | ACROS + G |
| `0x06` | Monochrome | | `0x10` | ETERNA / Cinema |
| `0x07` | Monochrome + Ye | | `0x11` | Classic Neg. |
| `0x08` | Monochrome + R | | `0x12` | ETERNA Bleach Bypass |
| `0x09` | Monochrome + G | | `0x13` | Nostalgic Neg. |
| `0x0A` | Sepia | | `0x14` | REALA ACE |

The numeric mapping follows rawji; FilmKit uses the same mapping, with `0x11`–`0x14` from tkcranny/fxraw, and fujicli has the same twenty values. This reference arranges and annotates those values for comparison with the evidence that follows. [Published: rawji] [Published: fujicli] Nine values in the range the sources dispute were menu-confirmed on an X-T50: PRO Neg. Hi `4`, PRO Neg. Std `5`, Monochrome `6`, Monochrome + Ye `7`, Sepia `10`, ACROS `12`, ACROS + Ye `13`, ACROS + R `14`, and ACROS + G `15`, each set by hand in a bank's menu and read back with no other property changing. [Measured: X-T50 fw 1.32, 2026-10-15] The table is also consistent with every bank read on the X-T50 and GFX100S, including the GFX100S owner's comparison of all six banks against the camera's own menu, and fujifilm-ptp-recipes' property table gives the same twenty values (that table names no body) [Published: fujifilm-ptp-recipes]. Which simulations a body offers depends on its model and firmware. Firmware updates add REALA ACE (`0x14`) to the X-T5, X-S20, and X-H2; [film simulations added by firmware](07-cameras.md#film-simulations-added-by-firmware) gives the versions. [Published: Fujifilm firmware notes] X RAW Studio's capability table records six strictly nested sets, from `1`–`15` through `1`–`20`, with the numbering unchanged. Its [per-body records](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xrfc-value-tables.md#L588-L617) assign the same X-H2 `1`–`19` and then `1`–`20` under different capability records, reflecting a firmware change [Published: fujifilm-ptp-recipes, static analysis]. A code the body lacks renders as PROVIA in a conversion. [Published: rawji] [Published: grawji]

The preceding capability-chain summary is adapted and condensed from [ILFforever/fujifilm-ptp-recipes' protocol-status discussion](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/protocol-status.md#L100-L104), whose documentation is [licensed under CC BY 4.0](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/LICENSE).

Two sources differ. fuji-ptp-notes' table orders values `4`–`10` differently (Monochrome `4`, Sepia `5`, PRO Neg. Hi `6`, PRO Neg. Std `7`, and the Monochrome filters `8`–`10`); the table carries no evidence mark, the only values it reports writing on its GFX100RF are the same in both orders, and the X-T50 sweep described earlier contradicts the order on hardware, so it might be a documentation error rather than a body difference. No GFX body has menu-confirmed this range here. fujifilm-ptp-recipes' two tables disagree with each other on whether `0x0D` is ACROS + Ye or ACROS + R, and the one it labels as verified on its X-H2 is the MakerNote table that has them swapped; the X-T50 sweep settles `0x0D` as ACROS + Ye. Both are in [errata](errata.md).

## `0xD193` / `0xD194` Monochromatic Color

Signed, ×10. `0x0014` = WC +2; `0xFFF6` = MG −1. [Owner report: GFX100S fw 2.13, menu-confirmed] WC +5 and MG −3 set by hand read `50` and `−30`, which fixes both the axis assignment and the scale. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes, menu-confirmed] Its sweep establishes a 10-step grid among the values it tried, not the endpoints: a write sweep took `0`, `10`, `20`, `50`, `90`, `100`, and `−90` and refused `1`, `2`, `5`, `9`, and `−9` with `0x201C`, identically on both codes. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]

An X-T50 under ACROS gives the same grid: `0`, `10`, `−10`, `180`, and `−180` accepted on both axes; `5`, `9`, `−9`, and `190` refused `0x201C`. [Measured: X-T50 fw 1.32, 2026-10-15]

Which bodies have which axes: Fujifilm's manuals give some bodies the warm–cool axis alone, as **B & W ADJ.** with a printed −9…+9 range, most later bodies both axes, and the oldest neither; [effect controls in the menus](07-cameras.md#effect-controls-in-the-menus) lists which among the bodies with protocol observations; the single-axis bodies are the X-T3, the X-T30, and the GFX100 before firmware 4.00, as the range table that follows records. [Published: Fujifilm manuals] Both axes are established here on the X-T50 [Measured: X-T50 fw 1.32, 2026-10-15], on the GFX100S, whose bank read WC +2 / MG −1 back in the camera's menu [Owner report: GFX100S fw 2.13, menu-confirmed], and on the X-H2 [Published: X-H2 fw 5.20, fujifilm-ptp-recipes, menu-confirmed]. FilmKit attributes both codes to captures; the [surrounding mapping comment names the X100VI](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/constants.ts#L80-L92), so that body attribution comes from the block's context [Published: FilmKit, body implied for these captures].

### Menu range per body

Wire values are menu values ×10. Keep tested points separate from demonstrated endpoints, and menu limits separate from USB acceptance and rejection:

| Body | Tested or reported values | Limits of the evidence | Evidence |
|--|--|--|--|
| X-T3, X-T30, GFX100 before fw 4.00 | Warm–cool only; menu −9…+9 | Manual range; no USB endpoint test here | [Published: Fujifilm manuals] |
| X-T50 fw 1.32 | Both axes: ±180 accepted, 190 refused. WC +18 / MG −18 written to a bank appears as +18 / −18 in **EDIT/SAVE CUSTOM SETTING** | Establishes −18…+18 for this body | [Measured: X-T50 fw 1.32, 2026-10-15] [Measured: X-T50 fw 1.32, 2026-10-17, menu-confirmed] |
| GFX100S fw 2.13 | Both axes: menu endpoints −18…+18, photographed at WC +18 / MG +18 and WC −18 / MG −18; WC 0 / MG +18 and WC 0 / MG 0 also shown | Menu limits confirmed; USB ±180 acceptance and out-of-range rejection remain untested here | [Owner report: GFX100S fw 2.13, menu photographs, received 2026-10-18]; [observations](../evidence/gfx100s-monochromatic-color-menu.md) |
| X-H2 fw 5.20 | Source reports menu −18…+18 and gives WC +18 / −18 MakerNote examples from isolation shots; its detailed USB sweep includes `100` and `−90` | Published range report; the detailed USB sweep does not test ±180 acceptance or out-of-range rejection | [Published: fujifilm-ptp-recipes — [range and sweep](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/properties.md#L224-L243), [MakerNote observations](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/exif-makernote.md#L154-L170)] |
| X-S10 (X-Processor 4), firmware unstated | `−180`, `0`, `180` read back on both axes and visually checked on the body. A Classic Chrome bank read `180`/`180` at rest | Three points, not a complete grid or maximum; `190` untried; historical verifier didn't retain write response codes | [Published: Filmcase] |
| X100V, X-T4, X-Pro3 | Both axes reported as −18…+18 | Firmware unspecified; no raw bytes | [Community: Fuji X Weekly, 2020-06-14] |
| X100V, X-T4, X-Pro3, X-S10 | grawji's capability table gives ±9 | No probe reported; contradicted by the preceding X-S10 readbacks | [Published: grawji] |
| X-T5, X-S20 | fujicli's schema gives ±18 | No probe reported | [Published: fujicli] |
| Other two-axis bodies, including GFX models with both axes other than the GFX100S | Manuals name both axes but print no endpoints | Range unestablished here | [Published: Fujifilm manuals] |

The numeric evidence fits “one axis −9…+9, two axes −18…+18”; this is a pattern, not a rule.

### Polarity and use

Positive WC is warm and positive MG is green, on the menu and in the MakerNote. [Community: Fuji X Weekly, X100V photographs] [Published: ExifTool forum] A GFX100S's menu agrees: WC +18 sits at the **WARM** end of its grid and MG +18 at the **G** end. [Owner report: GFX100S fw 2.13, menu photographs] X-T50 conversions at WC +7 and +18 render warm, and at MG −4 and −18 magenta, measured on the saved output files. [Measured: X-T50 fw 1.32, 2026-10-17] The [toning captures](../captures/x-rawstudio-toning-xt50.md) carry the transmitted cells and the output MakerNotes. [Captured: X-T50 fw 1.32, 2026-10-17] The wire sign matches the menu sign, as the earlier WC +2 / MG −1 and WC +5 / MG −3 readings show.

In the conversion profile the same values go in cells 23 (WC) and 26 (MG); see [the conversion profile](06-conversion-profile.md#monochromatic-color-cells-23-and-26).

In a JPEG's MakerNote the same settings are tags `0x1049` (WC) and `0x104B` (MG), signed 8-bit (`238` = −18). [Published: ExifTool forum] The MakerNote tags say nothing about the PTP properties.

Zero might differ by body. The X-T50 and the X-H2 accept `0` on a monochrome bank. fuji-ptp-notes marks its toning register rows as community-sourced, but its [GFX100RF experiment log](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/EXPERIMENTS.md#L23-L35) presents zero refusal, even on a monochrome simulation, as a result. It supplies no transaction trace, selected simulation, or numeric response for that refusal, so the claim's provenance is ambiguous. [Published: fuji-ptp-notes] FilmKit's code says an X100VI refuses `0` on `0xD193`, with no run described [Published: FilmKit]. Zero refusal on those bodies remains an [open question](open-questions.md#bank-protocol).

These apply only to monochrome simulations that offer toning: Monochrome and ACROS and their filter variants. The [X-T50 manual](https://fujifilm-dsc.com/en/manual/x-t50/menu_shooting/image_quality_setting/#monochromatic) and [X-S10 manual](https://fujifilm-dsc.com/en-int/manual/x-s10/menu_shooting/image_quality_setting/#monochromatic) name those two simulation families for Monochromatic Color. [Published: Fujifilm manuals] On a color simulation, the camera refuses the writes with `0x201C`. [Captured] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] fuji-ptp-notes also reports refusal, but gives no numeric response or detailed trial, and its register map and experiment log differ in how they present the evidence. [Published: fuji-ptp-notes] Sepia is monochrome, but the camera grays its toning controls out [Measured: X-T50, 2026-09-20], and on a Sepia bank every tested write to either axis is refused `0x201C`, `0` included [Measured: X-T50 fw 1.32, 2026-10-15].

The X-T3, the X-T30, and a GFX100 before firmware 4.00 have the warm–cool axis alone [Published: Fujifilm manuals] and presumably use only `0xD193` [Inferred]; none of them has shown the bank protocol over USB.

## `0xD195` Grain Effect

Grain has different value sets for reading and writing. [Measured: X-T50, 2026-08-01] [Owner report: GFX100S fw 2.13, 2026-09-15] [Published: fujifilm-ptp-recipes — `1` for Off, `6` read back for Off and refused as a write; no body named] [Published: GFX100RF, fuji-ptp-notes — the write set `1`–`5`] [Published: fujicli — its [historical grain comment](https://github.com/karaolidis/fujicli/blob/c0b4de7/src/camera/ptp/hex/fuji.rs#L143-L150) reports `1` reading back as `6` or `7`; the [contemporaneous README](https://github.com/karaolidis/fujicli/blob/c0b4de7/README.md#L5-L7) names the X-T5 as its sole tested body] [Published: grawji — factory banks on an X-E5 read `6`, and Off written over a Large-grain bank reads back `7`] [Published: X-S10, Filmcase — `6` and `7` read from banks; `1` written over a Strong + Large bank read back `7`, the body showing Off and Large; firmware unstated]

| Meaning | Write | Read back as |
|--|--|--|
| Off | `1` | `6` (size Small remembered) or `7` (size Large remembered) |
| Weak, Small | `2` | `2` |
| Strong, Small | `3` | `3` |
| Weak, Large | `4` | `4` |
| Strong, Large | `5` | `5` |

- The camera refuses writes of `0`, `6`, `7`, and `8` with `0x201C`. That includes `6` and `7`, the values the camera itself reports for Off. [Measured: X-T50 fw 1.32, 2026-09-14] [Owner report: GFX100S fw 2.13, 2026-09-15]
- A write of `1` gets an OK response and reads back as `6` or `7`. The camera keeps the grain size the bank last had, as its menus do while grain is Off.
- Decode `1`, `6`, and `7` all as Off. Verify a write of `1` by its Off meaning; its read-back can be `6` or `7`. Exact restoration of a saved state must also compare the remembered size.
- Direct writes of the saved Off values `6` and `7` are refused on the tested bodies. The sequences `2` (Weak/Small) → `1` (Off) → read `6` and `5` (Strong/Large) → `1` (Off) → read `7` were both demonstrated, with successful writes and read-backs, on an X-T50 and a GFX100S. These sequences reconstruct the two Off variants on those bodies. [Measured: X-T50 fw 1.32, 2026-09-14] [Owner report: GFX100S fw 2.13, 2026-09-15]
- Writing only `1` restores Off while retaining the then-current size. A recorded GFX100S rollback saved `6`, tested `5`, then wrote `1` and read `7`: Off was restored, but the saved size was not. The reconstruction sequences alone aren't a complete-bank rollback test; verify the final bank against its saved baseline. [Owner report: GFX100S fw 2.13, 2026-09-15]
- On an X-T50, `5` → `1` restored a saved `7` within a whole-bank rollback whose final read matched the saved baseline in every bank setting and the name; see [restoring a bank](04-custom-slots.md#restoring-a-bank). [Measured: X-T50 fw 1.32, 2026-10-18]

FilmKit's source also defines grain as `0x0000`/`0x0002`/`0x0003`/`0x0102`/`0x0103`. That is its internal UI representation, not a wire encoding. X RAW Studio builds the wire value the same way this table does, folding its separate grain-size field into one composite: Off is `1` whatever the size, then `2`–`5`. [Published: fujifilm-ptp-recipes, static analysis]

Fujifilm's manuals give eight bodies a strength-only **GRAIN EFFECT** (**STRONG**, **WEAK**, **OFF**): the X-T20, X-H1, X-T3, and X-T30, in [effect controls in the menus](07-cameras.md#effect-controls-in-the-menus), and the [X-T2](https://fujifilm-dsc.com/en/manual/x-t2/menu_shooting/image_quality_setting/index.html), [X-E3](https://fujifilm-dsc.com/en/manual/x-e3/menu_shooting/image_quality_setting/index.html), [GFX 50S](https://fujifilm-dsc.com/en-int/manual/gfx50s/menu_shooting/image_quality_setting/index.html), and [GFX 50R](https://fujifilm-dsc.com/en-int/manual/gfx50r/menu_shooting/image_quality_setting/index.html), which have no protocol observations; every later body has a **ROUGHNESS** and a **SIZE** item. [Published: Fujifilm manuals] None of the eight has shown the bank block over USB, so whether `0xD195` takes the size-bearing write values `2`–`5` there, or a different set, is untested; see [open questions](open-questions.md#bank-protocol).

## `0xD196` / `0xD197` / `0xD198` Color Chrome, Color Chrome FX Blue, Smooth Skin

One-indexed: `1` = Off, `2` = Weak, `3` = Strong. The conversion profile uses the same encoding. [Measured: X-T50] [Published: FilmKit] [Published: fujifilm-ptp-recipes] [Published: GFX100RF, fuji-ptp-notes — `0xD196` only; its other two mappings are relayed and not additional body evidence] Which bodies' menus list **COLOR CHROME EFFECT** and which list **COLOR CHROME FX BLUE** is in [effect controls in the menus](07-cameras.md#effect-controls-in-the-menus). [Published: Fujifilm manuals]

FilmKit stores these zero-indexed in its UI and adds one when writing. [Published: FilmKit] Don't copy the UI values to the wire.

## `0xD199` White Balance mode

Read unsigned.

| Value | Mode | Evidence |
|--|--|--|
| `0x0000` | Placeholder observed in as-shot conversion profiles with cell 11 = `1`; no bank meaning established here | [Published: libfuji profiles and [dummy-value definition](https://github.com/petabyt/libfuji/blob/a3bd237/fp/src/fp.h#L177-L196)] |
| `0x0002` | Auto | [Measured: X-T50] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x0004` | Daylight | [Captured] [Measured: X-T50] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x0006` | Incandescent | [Published: FilmKit] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x0008` | Underwater | [Published: FilmKit] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8001` | Fluorescent 1 | [Published: FilmKit] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8002` | Fluorescent 2 | [Owner report: GFX100S, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8003` | Fluorescent 3 | [Published: FilmKit] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8006` | Shade | [Published: FilmKit] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8007` | Color temperature (Kelvin in `0xD19C`) | [Measured: X-T50] [Published: libfuji capture] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] [Published: fuji-ptp-notes — lists this mode in an unmarked enumeration; no Kelvin trial condition documented] |
| `0x8008`, `0x8009`, `0x800A` | Custom 1, 2, 3 (a white balance measured and stored on the camera) | Custom 1 [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Captured: X-T50 fw 1.31, FilmKit #12 capture — `0x8008` in profile cell 12]; all three [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]. A body whose custom slot is empty might refuse the mode, so a refusal there is inconclusive. |
| `0x8020` | Auto, White Priority | [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| `0x8021` | Auto, Ambience Priority | [Published: FilmKit, X100VI] [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |

The [white balance and tone menu table](07-cameras.md#white-balance-and-tone-controls-in-the-menus) records which bodies offer Auto White Priority and Auto Ambience Priority alongside plain Auto. Every listed body has three custom white balance memories, Color Temperature, and Underwater. These are menu facts, not USB acceptance or encoding observations; the coverage excludes the X100F, whose manual is a PDF. [Published: Fujifilm manuals]

In a conversion profile, cell 11 selects the white balance source: `1` uses the RAF's as-shot balance and `2` uses the mode in cell 12. The inspected libfuji examples pair cell 12 = `0` with cell 11 = `1`; they do not isolate zero as an independent selector or test it on the bank path. See [the profile's source selector](06-conversion-profile.md#bank-properties-and-profile-cells).

All fourteen nonzero modes in the preceding table were written in turn, read back unchanged, and restored on an X-H2; that establishes that the values are accepted, not what each one means. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] fujicli lists the same values [Published: fujicli]. fuji-ptp-notes' [unmarked list](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/README.md#L233-L240) agrees on ten of those modes, omitting Underwater and Custom 1–3, and identifies no explicit source for the list. Filmcase separately attributes its values to Fujifilm's camera-control SDK header and reports matching readbacks for all fourteen on its X-S10 [Published: X-S10, Filmcase — firmware unstated]. The historical verifier didn't retain write response codes, and matching readbacks alone don't establish each mode's meaning. X RAW Studio's own label map also carries `0x9001` "as-shot white balance", which no capability set lists and no body has been seen to answer. [Published: fujifilm-ptp-recipes, static analysis]

## `0xD19A` / `0xD19B` White Balance shift

Signed, in the camera's own units, −9 to +9. Red −2, Blue −2 read as `−2`/`−2`. [Owner report: GFX100S, menu-confirmed] [Published: FilmKit] [Published: fujifilm-ptp-recipes] [Published: GFX100RF, fuji-ptp-notes — signed units measured; range relayed] These are the only two signed dials that aren't ×10.

The shift belongs to the white balance mode, within the bank. Each mode keeps its own shift, and `0xD19A`/`0xD19B` report the active mode's: changing only the mode in C7's menu changed the pair from `9`/`−9` (Daylight) to `2`/`−4` (Auto White Priority), `0`/`0` (Ambience Priority), `0`/`0` (Underwater), `−2`/`3` (Shade), `2`/`−6` (Fluorescent 1), `0`/`0` (Incandescent), `1`/`−4` (Auto), and `0`/`0` (Custom 1), each time with nothing else moving. [Measured: X-T50 fw 1.32, 2026-10-15] So you must write a recipe's shift after its white balance mode, which is the order X RAW Studio uses, and a read-back of the shift is only meaningful under the mode it was written for.

## `0xD19C` Color temperature

Unsigned, in kelvin (5300 K is `5300`). [Measured: X-T50 fw 1.32]

Write Kelvin with `0xD199` set to `0x8007`. FilmKit's [README attributes this prerequisite](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/README.md#L60-L65) to its Wireshark captures of an X100VI, without describing the trial [Published: FilmKit, X100VI captures]. In the public X-T50 save, `0xD19C = 0` was refused `0x201C` while Daylight was selected. Because `0` is also outside the published Kelvin range, that transaction does not isolate the mode as the cause. None of the seven public FilmKit #12/#13 captures tests a valid Kelvin value under a non-Kelvin mode. [Captured: X-T50 fw 1.31, FilmKit #12, tid 1809] The bank-mode gate remains an [open question](open-questions.md#bank-protocol). fuji-ptp-notes states the rule without a measured basis [Published: fuji-ptp-notes — unmarked rule]; fujifilm-ptp-recipes applies it as a bank-writer policy and reports the refusal on live `0xD017` on its X-H2, a separate body and property path [Published: fujifilm-ptp-recipes].

While white balance is anything else, the bank keeps the last Kelvin value written. The camera shows it grayed out and uses it for nothing. [Measured: X-T50 fw 1.32, 2026-09-20] X RAW Studio's capability table gives older bodies a list of 31 fixed Kelvin values and newer ones, the X-T50 included, any value from 2500 to 10000 in steps of 10; which bodies fall on which side is in that project's tables. [Published: fujifilm-ptp-recipes, static analysis] [Published: fujicli — 2500–10000 in steps of 10 on an X-T5]

The [white balance and tone menu table](07-cameras.md#white-balance-and-tone-controls-in-the-menus) records the per-body Kelvin bounds, command-dial increments, and cases where the manual gives only a displayed list. [Published: Fujifilm manuals] It also records the X-T3 support article's 2500–10000 K range. [Published: Fujifilm support article, X-T3] These statements describe the menu, not USB acceptance; no write at either bound is recorded here.

X RAW Studio writes Kelvin straight after the white balance mode and before the shifts. fujicli's writer places the shifts first; the project is tested on an X-T5 but publishes no specific Kelvin/shift-retention result [Published: fujicli]. On an X-S10 a Kelvin write sent after the shifts set both shifts to `0`, with the mode already Kelvin [Published: X-S10, Filmcase — firmware unstated], so keep X RAW Studio's order; whether the X-T50 behaves like the X-S10 is an [open question](open-questions.md#bank-protocol).

## `0xD19D` / `0xD19E` / `0xD19F` / `0xD1A0` / `0xD1A2` Tones, Color, Sharpness, Clarity

Signed, ×10. Half steps exist: `0x000A` = +1, `0x0005` = +0.5, `−20` = −2. [Owner report: GFX100S, menu-confirmed] [Measured: X-T50] [Published: fujifilm-ptp-recipes — no body named for the examples] [Published: GFX100RF, fuji-ptp-notes — the signed ×10 reading] [Captured: X-T50 fw 1.31, FilmKit #12 capture — Highlight +1 as `10`, Sharpness −2 as `−20` in profile cells 16 and 19] Tone step size depends on the body and firmware. X RAW Studio's [tone variants](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xrfc-value-tables.md#L317-L328) give half steps to the X-T4, X-S10, X-E4, X-T30 II, GFX100S, GFX 50S II, and every listed X-Processor 5 body. The [GFX100 capability records](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xrfc-value-tables.md#L604-L620) change from whole steps in `_0100`/`_0200` to half steps in `_0300`; those suffixes are capability keys, not necessarily public firmware version numbers. [Published: fujifilm-ptp-recipes, static analysis]

The [white balance and tone menu table](07-cameras.md#white-balance-and-tone-controls-in-the-menus) records the manual's per-body Highlight and Shadow ranges, whether they share a **TONE CURVE** item, and whether a step size is printed. [Published: Fujifilm manuals] These menu statements are separate from the USB observations and X RAW Studio capability records earlier in this section.

FilmKit treats `0x8000` (−32768) as "no value" [Published: FilmKit]. grawji's [observation comment](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/preset_recipe.py#L67-L69) reports it from tone/NR reads for values a bank never stored, without identifying the bodies. Its [verifier policy](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/preset_recipe.py#L245-L255) also tolerates it for Color, Sharpness, Clarity, and both toning axes; that broader list does not establish observations from each property. [Published: grawji] The sentinel interpretation collides with the valid NR −4 encoding. No uninitialized-value use has been established in a bank here.

- The camera refuses Color (`0xD19F`) while a monochrome simulation is active, even a write of the value already there. [Measured: X-T50 fw 1.32, 2026-10-03, with ACROS active]
- The camera refuses Highlight and Shadow Tone while D-Range Priority is on. [Measured: X-T50 fw 1.32, 2026-09-18] See [the interlock](04-custom-slots.md#the-d-range-priority-interlock).
- On the X-T50, Clarity (`0xD1A2`) was refused for every tested value while the bank's file format was HEIF, including its held value, and accepted on a JPEG bank in the same session. [Measured: X-T50 fw 1.32, 2026-10-15] Separately, fuji-ptp-notes' [original experiment notes](https://github.com/Junsudo/fuji-ptp-notes/blob/d453df2/README.md#L135-L136) report refusals while its GFX100RF was on HEIF and acceptance after switching to JPEG; it doesn't identify bank versus live format, the held-value test, or a same-session bank comparison. [Published: GFX100RF, fuji-ptp-notes] The format is a bank setting outside the 23 properties: `0xD18F` read `4` under both. The X-T50 and X-E5 manuals say HEIF also forces **COLOR SPACE** to sRGB [Published: Fujifilm manuals], so a HEIF bank might hold `0xD1A4 = 1` and refuse `2`; untested (see [open questions](open-questions.md#bank-protocol)). Which bodies' menus list **CLARITY** is in [effect controls in the menus](07-cameras.md#effect-controls-in-the-menus). [Published: Fujifilm manuals]

## `0xD1A1` High ISO Noise Reduction

A non-linear lookup. Read unsigned. fujifilm-ptp-recipes and fujicli give the same nine values, and libgphoto2 reads the live twin `0xD01C` as `0x8000`, `0x2000`, and `0x5000` for −4, 0, and +4 on an X-T5. [Published: fujifilm-ptp-recipes] [Published: fujicli] [Published: libgphoto2] The list fuji-ptp-notes carries is Filmcase's: on its X-S10, −4, −2, and 0 were read from named banks and all nine listed values reportedly read back as written [Published: X-S10, Filmcase — firmware unstated].

| Setting | Wire | Evidence |
|--|--|--|
| −4 | `0x8000` | [Measured: X-T50] [Owner report: GFX100S, menu-confirmed] |
| −3 | `0x7000` | [Published: FilmKit] |
| −2 | `0x4000` | [Published: FilmKit] |
| −1 | `0x3000` | [Owner report: GFX100S, menu-confirmed after a write] |
| 0 | `0x2000` | [Measured: X-T50] [Owner report: GFX100S] |
| +1 | `0x1000` | [Published: FilmKit] |
| +2 | `0x0000` | [Published: FilmKit] |
| +3 | `0x6000` | [Published: FilmKit] |
| +4 | `0x5000` | [Published: FilmKit] |

## `0xD1A3` Lens Modulation Optimizer, `0xD1A4` Color Space

`0xD1A3` is Lens Modulation Optimizer, not FilmKit's Long Exposure NR: toggling **LENS MODULATION OPTIMIZER** in a bank's menu moves it between `1` and `2` and nothing else, and toggling **LONG EXPOSURE NR** moves nothing in the block. `0xD1A4` Color Space moves between `1` and `2` the same way. [Measured: X-T50 fw 1.32, 2026-10-15] For `0xD1A3`, `1` = **ON** and `2` = **OFF**: a bank reading `2` shows **OFF** in the menu. [Measured: X-T50 fw 1.32, 2026-10-15] [Published: fujicli — On `1`, Off `2`] For `0xD1A4`, `1` = sRGB and `2` = Adobe RGB, each set by hand and read back. [Measured: X-T50 fw 1.32, 2026-10-15, menu-confirmed] The conversion profile carries the same two settings in cells 21 and 22 with the same values; the recovered JPEG metadata follows them through `LensModulationOptimizer` and `InteropIndex`. This checks the metadata, not the image-processing effect on pixels. [Captured: X-T50 fw 1.31 and X-T30 fw 2.01, FilmKit #12 and #13 captures] X RAW Studio writes `1` to both when saving a bank [Captured]; fujicli's code comment reports a write to `0xD1A3` being refused while no lens is attached, without identifying the body [Published: fujicli code comment]. Carry them through unchanged; fujifilm-ptp-recipes reads and logs both without writing them, and fuji-ptp-notes doesn't write `0xD1A4`.

## `0xD1A5`, X RAW Studio's live Image Size

Not a bank setting in X RAW Studio's model. In the captured combined save it follows `0xD1A4`, with `0xD18E`'s value, as the first of 23 live writes; the bank reader never reads it. [Captured: X-T50 fw 1.31, FilmKit #12 capture] The peer's static analysis makes this live copy optional. [Published: fujifilm-ptp-recipes, static analysis] Separate matching `0xD18E`/`0xD1A5` readings (`7`/`7`) were seen on the X-T50, and `14`/`14` reported across six GFX100S banks. [Measured: X-T50] [Owner report: GFX100S] In X RAW Studio's captured save, both transmitted writes carried `9`, but only `0xD18E` was subsequently read back; `0xD1A5` wasn't read. [Captured: X-T50 fw 1.31, FilmKit #12 capture] Neither the separate matching readings nor the matching writes prove a shared store or explain the matches. fuji-ptp-notes lists `0xD1A5 = 7` without a measured basis or a comparison to `0xD18E`; the X-T30 II report has `0xD1A5 = 7` while `0xD18E` varies. [Published: fuji-ptp-notes — unmarked report] [Community: fujifilm-ptp-recipes PR #2]

What the camera does with the write is open. On an X-T50 nothing the menus do moves it: saving a bank's Image Size as L 16:9, L 1:1, M 3:2, and S 3:2 in turn left it at `7` while `0xD18E` read `8`, `9`, `4`, and `1`; a USB write of `9` to `0xD18E` left it at `7`; setting the live Image Size to L 1:1 on the body left it at `7`; and writing `7` to it left the body showing L 1:1. [Measured: X-T50 fw 1.32, 2026-10-15] Whether it's writable depends on the body: the X-T50 accepts it [Captured] [Measured: X-T50 fw 1.32, 2026-10-15]; the GFX100S refuses `0x201C` even for a write of its current value [Owner report]; an X-H2 accepted a write moving it from `7` to `8` [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]. A bank-only writer leaves it alone. A writer that mirrors X RAW Studio's live copy sends it after the bank with `0xD18E`'s value, never a different one, expects some bodies to refuse it, and restores the live state it changed. See [open questions](open-questions.md#bank-protocol).

## `0xD18D` Bank name

A PTP string (see [framing](01-transport.md#ptp-framing)). Names of up to 25 characters of printable ASCII (`0x20`–`0x7E`) round-trip and show correctly in the camera's own menu. That was tested with a 25-character name containing quotes, a backslash, and a backtick. [Measured: X-T50, 2026-09-07] The X-H2 source says the camera's name entry appears to stop at 25 characters; it does not establish a USB limit. fujifilm-ptp-recipes' safe set is printable ASCII without the backtick, which round-tripped here. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] fujicli also declares 25 characters. [Published: fujicli] A GFX100RF answered `0xA001` (a vendor-specific response) during a name-length probe. The fuji-ptp-notes [name-length note](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/README.md#L299) advises shortening the name but gives no failing payload or length, so the cause and limit remain unestablished; read the name back. [Published: GFX100RF, fuji-ptp-notes] An unnamed X-T50 bank answers three bytes, a count of `1` and the NUL, rather than the one-byte empty string. [Published: FilmKit issue #12 log, X-T50 fw 1.31] Over direct USB, a write of the one-byte empty string `00` to a named bank is accepted with `0x2001`, and the bank then answers those same three bytes; its menu labels the bank **CUSTOM 7** and opens a blank name editor ([sanitized package](../evidence/xt50-20261019-102738/README.md)). [Measured: X-T50 fw 1.32, 2026-10-19] A write of the three-byte form `01 00 00` is accepted with the same result. With either form the bank still answers `01 00 00` after a Film Simulation write and after writing it back, and writing the original name's bytes restores the name ([sanitized package](../evidence/xt50-20261019-133848/README.md)). [Measured: X-T50 fw 1.32, 2026-10-19] Through ImageCaptureCore on iOS, the one-byte write to a named bank, followed by 20 bank-setting writes, is also accepted with `0x2001`, but the name read after those writes is the one the bank held before ([sanitized package](../evidence/xt50-20261019-125007/README.md)). [Measured: X-T50 fw 1.32, iOS 27.0.1, 2026-10-19] Over the same transport, the three-byte form `01 00 00` written to a named bank, followed by 19 bank-setting writes, is accepted with `0x2001`, and the bank then answers `01 00 00` ([sanitized package](../evidence/xt50-20261019-140542/README.md)). [Measured: X-T50 fw 1.32, iOS 27.0.1, 2026-10-19] On this body, then, the three-byte form clears a name over both transports, and the one-byte form only over direct USB. Setting writes after an empty name don't undo it over direct USB, and what ImageCaptureCore sends for a one-byte data phase isn't observed; see [open questions](open-questions.md#bank-protocol). Characters outside printable ASCII aren't characterized; fujifilm-ptp-recipes folds accents to ASCII and strips the rest before writing, without claiming any of them fail.
