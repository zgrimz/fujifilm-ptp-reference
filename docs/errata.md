# Corrections to published sources

This page lists where a published source disagrees with hardware, with a capture of Fujifilm's own software, or with another published source. Each entry says what the source says, what the evidence shows, and how sure that is. These projects are the foundation this record is built on, or independent records it has been checked against (for details, see [`SOURCES.md`](../SOURCES.md)). The point is to save the next reader from rediscovering the same disagreements.

## FilmKit

### `0xD185` cell 11 is the white balance source, not Smooth Skin

FilmKit names cell 11 `SmoothSkin` and writes the Smooth Skin value plus one into it. Cell 11 decides whether a conversion uses the RAF's as-shot white balance (`1`) or the mode in cell 12 (`2`), so writing a Smooth Skin value there silently switches the conversion's white balance source. Smooth Skin is cell 24. Evidence: libfuji's captures and field names (an X-H1 as-shot profile with cells 11/12 = `1`/`0`; an X-Pro3 Kelvin conversion with `2`/`0x8007` and 2200 K in cell 15), X RAW Studio's editor walk changing cell 24 for Smooth Skin [Captured], and X-T50 hardware. The error remains in both FilmKit and its macnow fork.

### `0xD185` cell 4 is Image Quality; Exposure Bias is cell 5

FilmKit's table puts Exposure Bias at cell 4, so it writes EV × 1000 into the Image Quality cell. Evidence: X RAW Studio's editor walk changes cell 4 for **FINE**/**NORMAL** and cell 5 for push/pull [Captured], rawji's field map, and libfuji's captures. The macnow fork moved Exposure Bias to cell 5 in April 2026, and an X100VI user in FilmKit issue #6 confirms the round trip works there.

### FilmKit's `0xD185` table omits cells 22, 23, 24, and 26

FilmKit's `0xD185` table omits cells 22, 23, 24, and 26 (Color Space, Monochromatic Color warm–cool, Smooth Skin, and Monochromatic Color magenta–green), and its code states that Monochromatic Color isn't in the profile at all. X RAW Studio writes values into all four in the bank-copy or editor captures; the toning observations are editor changes, not a direct bank-copy experiment [Captured], and the toning cells render [Measured: X-T50].

### The grain values in FilmKit's `enums.ts` aren't a wire encoding

`0x0000`/`0x0002`/`0x0003`/`0x0102`/`0x0103` are FilmKit's internal representation. On the wire, `0xD195` accepts `1`–`5` and reads Off back as `6` or `7`. Evidence: [Measured: X-T50] [Owner report: GFX100S].

### FilmKit's D-Range Priority table is for conversion-profile cell 7

FilmKit's D-Range Priority table (Off 0 / Auto 1 / Weak 2 / Strong 3) is for conversion-profile cell 7, which FilmKit itself calls speculative. It never applies the table to `0xD191`, which it labels unknown. The bank property is Off 0, Weak 1, Strong 2, and Auto `0x8000` [Measured: X-T50] [Owner report: GFX100S]. Cell 7 is open, and libfuji and fujicli give it a different table. For details, see [the conversion profile](06-conversion-profile.md#d-range-priority-cell-7--unknown).

### `0xD1A3` is Lens Modulation Optimizer, not Long Exposure NR, and its Off value is `2`, not `0`

FilmKit names it Long Exposure NR and decodes `0` as Off. Toggling **LENS MODULATION OPTIMIZER** in a bank's menu moves `0xD1A3` between `1` and `2` and nothing else, a bank reading `2` shows **OFF**, and toggling **LONG EXPOSURE NR** moves nothing in the block. [Measured: X-T50 fw 1.32, 2026-10-15] X RAW Studio's own field for this code is `lLMOMode`, its live twin `0xD34D` is libgphoto2's "LMO mode", and fujicli and libfuji name it the same way with the same `1`/`2`. [Published: fujifilm-ptp-recipes, static analysis] [Published: fujicli] [Published: libfuji] grawji repeats FilmKit's name.

### `0x8000` in `0xD1A1` is NR −4, not a sentinel

FilmKit's constants call `0x8000` a sentinel that is never stored in presets, while its own NR table decodes it as −4. An X-T50 and a GFX100S store `0x8000` for NR −4, menu-confirmed. [Measured: X-T50] [Owner report: GFX100S]

### FilmKit triggers every conversion with `0xD183 = 0`, the reduced render

FilmKit triggers every conversion with `0xD183 = 0`, the reduced render, while its README promises a full-quality JPEG. The `1` full / `0` reduced / `2` refused semantics come from a third party's X-T50 test in its issue #15, not from its code. [Published: FilmKit]

### FilmKit's live-property labels are wrong

FilmKit's constants label `0xD007` color temperature, `0xD00A` noise reduction, `0xD00B` image quality, and `0xD017` grain. The live write in the issue #12 capture carries the bank's Dynamic Range to `0xD007`, its shifts to `0xD00B`/`0xD00C`, its Kelvin to `0xD017`, and its Image Quality to `0xD018`, matching libgphoto2's and the peers' names. [Captured: X-T50 fw 1.31]

### "`0xD19C`, `0xD19F` and `0xD1A1` are read-only"

This is a comment in FilmKit's source. It names no body, and FilmKit's own writer sends all three. On an X-T50 and a GFX100S, all three take writes when their conditions hold: Kelvin with Kelvin white balance selected, Color only on color simulations, and NR always. The captured X-T50 Kelvin refusal used `0` under Daylight and does not establish mode exclusivity; see [the Kelvin evidence](03-encodings.md#0xd19c-color-temperature). A refusal FilmKit saw was probably one of these conditions. [Inferred]

## macnow/filmkit

### A DR write doesn't corrupt a render as such

The fork stops writing cell 6, saying any DR write on a DR100 shot turns the output green or yellow. A DR equal to or lower than the frame's own renders clean; only a higher one doesn't. [Captured: X-T50 fw 1.32, 2026-09-07 conversion capture, X RAW Studio writing 200 onto a DR400 frame] [Measured: X-T50]

## rawji

### The `0x201` base and rawji's indices are consistent with each other, but not with FilmKit's

rawji places index 0 at `0x201`; FilmKit places its index 0 at `0x1FD` and numbers one higher. Both address the same bytes. The trouble comes from combining one project's base with the other's indices. The fixed base is `0x1FD`. For details, see [the conversion profile](06-conversion-profile.md#numparams-means-different-things-in-each-direction).

### rawji's IOPCode test misses an X-Processor 5 body

rawji tests `(iopcode & 0x00FFFF00) == 0x00179500` for "X-Processor 5". One X-Processor 5 body fails it: the X-T50 (`FF189504`, measured). The X-T5 passes (`FA179502` in X RAW Studio's own saved profile, `FF179502` read by fujicli), as does the X-H2's `0xD184` (`FF179501`). The X-H1 and the X100F, both X-Processor Pro, share `12`; the GFX100S (X-Processor 4) has `14` and the X-Pro3 `15`. The byte varies within a generation. The listed generation groups are disjoint, so these examples do not establish a cross-generation collision; no general decoder for unfamiliar codes is established. See [the IOPCode evidence](06-conversion-profile.md#the-iopcode).

### rawji writes a UI enumeration into cell 6 and `0` into cell 11

rawji rebuilds every profile from defaults rather than patching the camera's, so each conversion sends cell 6 = `1`, `2`, or `3` for DR100/200/400, cell 11 = `0`, and cell 1 = `2`. The established non-HDR cell-6 encoding here is the percentage `100`, `200`, or `400` [Measured: X-T50]; what rawji's `1`, `2`, and `3` render as is untested here. Cell 11 takes `1` or `2` [Published: libfuji] [Measured: X-T50]; what `0` does is untested.

### rawji's toning-range notes are wrong

rawji calls magenta–green an X-Processor 5 control and gives warm–cool ±9 on X-Processor 4. Fujifilm's manuals give both axes to every X-Processor 4 body from the X-Pro3 on, and a GFX100S (X-Processor 4) read MG −1 back from its menu. [Published: Fujifilm manuals] [Owner report: GFX100S fw 2.13, menu-confirmed]

### Cell 21 isn't reserved

rawji names it `Reserved20`; it's Lens Modulation Optimizer. [Captured: X-T50 fw 1.31, X-T30 fw 2.01]

## libfuji

### Color Chrome FX Blue in the conversion profile is one-indexed

libfuji's profile code enumerates it as Off `0`, Weak `1`, and Strong `2`, and validates cell 25 against that. The X-T50 fw 1.31 editor walk changes cell 25 from `2` Weak to `3` Strong [Captured]; rawji defines `1` Off, `2` Weak, and `3` Strong from its capture analysis [Published: rawji]. The observed bank/profile values match; this does not establish whether X RAW Studio copies them or independently serializes the same setting. See [the bank/profile comparison](06-conversion-profile.md#bank-properties-and-profile-cells).

### libfuji's color-space table doesn't match the camera

libfuji lists `1` sRGB, `2` "Adobe sRGB?", and `3` Adobe RGB, marked as unsure. `0xD1A4` and cell 22 are `1` sRGB and `2` Adobe RGB. [Measured: X-T50 fw 1.32, menu-confirmed] [Captured: X-T50 fw 1.31, X-T30 fw 2.01]

### libfuji's `xt5_*` filenames conflict with the profile bytes; the body is unconfirmed

The files are 601 bytes, 23 cells, and IOPCode `FF129504`; X RAW Studio's own saved profiles in libfuji's tree give that code to an X100F and `FA179502` to an X-T5, fujicli reads an X-T5 as `FF179502` with 29 cells, and an X-T5 has the Clarity, Color Chrome FX Blue, and toning cells a 23-cell profile lacks. The files are consistent with an X100F, but their original provenance hasn't been confirmed. [Published: libfuji] [Published: fujicli] [Inferred: candidate body]

## libfuji and rawji, both

### Dynamic range has an Auto value on the bank surface

Both projects model dynamic range as percentages (or a 1/2/3 UI enumeration) with no Auto. No working Auto encoding is established for the conversion profile here, while `0xD190` holds `0xFFFF` for DR Auto. [Measured: X-T50] [Owner report: GFX100S] Neither project writes camera banks, so neither would have met it.

## libgphoto2

### `0xD029` is Color Chrome Effect, not "Shadowing"

libgphoto2 keeps the older name; its own X-T5 commit notes the property behaved as Color Chrome Effect, and X RAW Studio writes the bank's Color Chrome Effect to it. [Published: libgphoto2] [Captured: X-T50 fw 1.31]

## fujifilm-ptp-recipes

fujifilm-ptp-recipes is an independent record of the bank protocol on an X-H2 and an X-T5 (fw 4.20), and a static analysis of X RAW Studio. It gives its X-H2 firmware as 5.20 in tested-body and experiment reports and 2.00 in reverse-engineering bench descriptions. Keep each observation's stated firmware; those descriptions do not establish that every experiment used the same version. The following entries list disagreements and evidence limits.

### X-H2 live-write coverage conflicts within the source

The [live verification report](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/current-shooting-state.md#L112-L123) reports changed-value writes, readback, and restoration for all 23 live codes. The [status page](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/protocol-status.md#L116-L121) leaves live LMO `0xD34D` write verification open. These statements cannot establish unqualified all-23 coverage together. Preserve the reported results and the conflict until the author clarifies the scope or supplies the missing trace. See [transport](01-transport.md#the-advertised-lists-are-not-complete).

### Stored DR Auto is `0xFFFF` on the tested X-T50; the X-H2 needs separate interpretation

fujifilm-ptp-recipes gives `0` for DR Auto, and reads the `0xFFFF` its X-H2 answers for `0xD190` while D-Range Priority is active as a placeholder rather than a stored value. Here `0xFFFF` is what a bank whose menu says **AUTO** stores, with the priority off: established by a menu sweep on an X-T50 and menu-confirmed on a GFX100S, read from an X-S10's bank by Filmcase, and reported from an X-T30 II with the priority Off in the source's own unmerged pull request #2. [Measured: X-T50 fw 1.32] [Owner report: GFX100S fw 2.13] [Published: X-S10, Filmcase] [Community: X-T30 II] On an X-T50, the camera refuses `0` with `0x201C` but accepts `0xFFFF` and `100` moments apart, and a bank holding DR100 keeps reading `100` after the priority is set to Strong in the menu. Together with the menu sweep, that establishes `0xFFFF` as a stored Auto value on the tested X-T50. [Measured: X-T50 fw 1.32, 2026-10-15] The source already reports controlled Auto/Off write tests for the X-H2 [bank properties](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/properties.md#L96-L106) and their [live counterparts](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/current-shooting-state.md#L79-L81); it also reports an active-priority `65535` reading interpreted as a placeholder. The X-T50 bank test here doesn't overturn those X-H2 observations. The published [bank example](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/protocol.md#L306-L319) preserves the previous DR value under Weak without giving it numerically; the numeric Off/Auto read trace remains unavailable for independent verification of the bank placeholder interpretation. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]

### `0xD1A5` is X RAW Studio's live Image Size, as the source says

The X-T50 test showed no visible Image Size change. fujifilm-ptp-recipes counts the bank block as 23 properties ending at `0xD1A4` and places `0xD1A5` on the live path from X RAW Studio's code. The capture agrees: X RAW Studio writes it first among its 23 live writes, with `0xD18E`'s value, in live-write time. [Captured: X-T50 fw 1.31] On an X-T50, setting the body's live Image Size to L 1:1 left `0xD1A5` at `7`, and writing `7` to it left the body showing L 1:1 [Measured: X-T50 fw 1.32, 2026-10-15]. That test doesn't establish whether the camera ignored, stored, or conditionally applied it; its effect remains open. This isn't a disagreement with the source, but an observation it didn't make.

### fujifilm-ptp-recipes' two film simulation tables disagree on `13` and `14`

The property table gives `13` ACROS + Ye and `14` ACROS + R; its MakerNote mapping, the one it labels as verified on its X-H2, gives the reverse. The property table is right: ACROS + Ye set by hand reads `13` and ACROS + R reads `14`. [Measured: X-T50 fw 1.32, 2026-10-15]

### A settle delay after selecting a bank is a precaution, not a measured need

fujifilm-ptp-recipes recommends about 100 ms before reading, with 50 ms found clean on the X-H2. In the X-T50 fw 1.31 save capture, the name command starts 4.676 ms after the selector command starts, including 4.291 ms selector latency and only 0.385 ms idle after its response. [Captured] This save has no substantial settling pause; it does not establish a minimum safe delay for all bodies. See [timing](01-transport.md#timing).

### Two static-analysis claims disagree with the captures

fujifilm-ptp-recipes says X RAW Studio never re-reads to verify a write, and that the SDK doesn't use `0xD185`. X RAW Studio re-reads every bank about 2 s after a save, and reads and writes `0xD185` for every conversion. [Captured: X-T50 fw 1.31 and 1.32] The SDK-level claims might hold for the layer it analyzed.

## fuji-ptp-notes

fuji-ptp-notes is a GFX100RF register map measured through ImageCaptureCore on macOS 26 and iOS 26. The source marks each register row as measured or community; most of its value tables carry no mark, and its own credits trace several (the D-Range Priority values, the NR table, and the ranges) to Filmcase, an X-S10 project that this record cites directly. This record distinguishes items explicitly marked measured from community, unmarked, and disputed-provenance reports at GFX100RF scope. The following entries list the disagreements.

### Film simulation values `4`–`10` are in a different order

The fuji-ptp-notes table gives Monochrome `4`, Sepia `5`, PRO Neg. Hi `6`, PRO Neg. Std `7`, and the Monochrome filters `8`–`10`. rawji, fujicli, fujifilm-ptp-recipes' property table, and this record give PRO Neg. Hi `4`, PRO Neg. Std `5`, Monochrome `6`, its filters `7`–`9`, and Sepia `10`, and an X-T50 menu sweep of PRO Neg. Hi, PRO Neg. Std, Monochrome, Monochrome + Ye, and Sepia gives `4`, `5`, `6`, `7`, and `10`. [Measured: X-T50 fw 1.32, 2026-10-15] The source's table carries no evidence mark, and the only film simulation values it reports writing on its body (`11`, `17`) are the same in both orders, so this might be a documentation error rather than a body difference. Its toning-gate list uses the same numbering, so, read in this record's order, it names PRO Neg. Hi and Sepia and omits Monochrome and Monochrome + Ye. The GFX100S menu comparison covered PROVIA banks only, so no GFX body has confirmed the range either way; a GFX100RF bank set to PRO Neg. Hi by hand and read over USB would show whether that body really differs.

### An X-T50 advertises the live settings in USB RAW CONV. mode

fuji-ptp-notes reports them not advertised in that mode on the GFX100RF, from either host. The X-T50 advertises all 20 live twins the source maps, and the captured combined save writes them on the optional live-copy branch. [Captured: X-T50 fw 1.31] Whether the GFX100RF answers them unadvertised there is open.

### iOS doesn't always refuse unadvertised properties

fuji-ptp-notes concludes that iOS's imaging stack answers `0x200A` for unadvertised properties from its GFX100RF tether-mode comparison. The concrete C7 `D192 = 11` trial and advertised `D18D` control do not establish an exhaustive range sweep or the rejecting endpoint. A later edit removed the phone-versus-camera hedge without adding published supporting evidence. On iOS 26 in **USB RAW CONV.** mode, a GFX100S answered all 26 unadvertised codes `0xD18C`–`0xD1A5`: selector, name, 23 bank settings, and live Image Size. An X-T20 separately answered an unadvertised `0xD183` descriptor; its original log does not record the USB mode. [Owner report: GFX100S fw 2.13] [Owner report: X-T20 fw 2.01] [Platform notes](09-platform-notes.md#unadvertised-properties-macos-forwards-them-ios-might-not) records the controls and missing wire evidence.

### A zero on the Monochromatic Color axes

The source lists `0` as refused on `0xD193`/`0xD194` even on a monochrome simulation. Its [original register row](https://github.com/Junsudo/fuji-ptp-notes/blob/d453df2/README.md) marks that claim community-sourced, and the [pinned register map](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/README.md#L163-L164) retains community marks for both axes. Its [GFX100RF experiment log](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/EXPERIMENTS.md#L23-L35), however, presents zero refusal as a result. No transaction trace, selected simulation, or numeric response accompanies it. The source therefore presents conflicting provenance, rather than no claim of a GFX100RF result. An X-H2 accepted `0` in a write sweep [Published: X-H2 fw 5.20, fujifilm-ptp-recipes], and so does an X-T50 under ACROS [Measured: X-T50 fw 1.32, 2026-10-15]. Whether the GFX100RF differs remains open.

### `0x2002` is General Error

The source names it InvalidObjectHandle, which is `0x2009`.

### `0xD1A4` as a JPEG/HEIF selector

fuji-ptp-notes recorded it so from a bank whose Clarity was grayed out, then demoted the reading in favor of Color Space based on FilmKit, fujicli, and libfuji's separate file-type field. This record includes it only so nobody re-derives it; `0xD1A4` is Color Space, menu-confirmed [Measured: X-T50].

## fujicli

### fujicli's color-space values are reversed

fujicli maps `0xD1A4` and profile cell 22 as sRGB `2` and Adobe RGB `1`. On an X-T50, `1` is sRGB and `2` Adobe RGB, menu-confirmed, and cell 22 = `1` renders an sRGB (R98) JPEG. [Measured: X-T50 fw 1.32, 2026-10-15] [Captured: X-T50 fw 1.31, X-T30 fw 2.01] fujicli's own early note that every X-T5 bank read `1` (the factory default is sRGB) supports the same mapping.

### Two things in fujicli's code aren't camera facts

Its grain table [once accepted `6` and `7` as Off](https://github.com/karaolidis/fujicli/blob/c0b4de7/src/camera/ptp/hex/fuji.rs#L143-L150) (noting that a write of `1` on an X-T5 reads back as `6` or `7`) and no longer does; and its `0xD190` value `0x640` for HDR800+ is, by its own comment, a convenience the camera never uses.

## Filmcase

Filmcase is an X-S10 project (GPL-3.0), explicitly credited by fuji-ptp-notes for D-Range Priority values, the NR table, and ranges. Its reported bank values and selected write/readback cases agree with this record. Two notes in it don't.

### Positive magenta–green is green; Sepia bank writes and EXIF need separate evidence

Filmcase's EXIF notes give positive magenta–green as magenta and list Sepia among the simulations with toning values; neither is marked as observed. Positive MG renders green [Measured: X-T50 fw 1.32, 2026-10-17]. A Sepia bank refused every tested write to the toning axes on an X-T50 [Measured: fw 1.32, 2026-10-15]; that refusal doesn't establish whether Sepia JPEGs carry toning tags or inactive values. Fujifilm's [X-T50 manual](https://fujifilm-dsc.com/en/manual/x-t50/menu_shooting/image_quality_setting/#monochromatic) and [X-S10 manual](https://fujifilm-dsc.com/en-int/manual/x-s10/menu_shooting/image_quality_setting/#monochromatic) explicitly describe toning for ACROS and MONOCHROME, supporting that applicability distinction.

### Direct bank access does not work on every tested X-Trans IV body

Filmcase expects every X-Trans IV body to work from the property codes alone, the X-T3, X-T30, and X-Pro3 included. The block failed in the supplied tests or reports for all three. For details, see [camera bodies](07-cameras.md).

## grawji

### `0xD1A3` is Lens Modulation Optimizer

grawji repeats FilmKit's Long Exposure NR label. [Measured: X-T50 fw 1.32, 2026-10-15]

### A body that doesn't advertise `0xD18C` might still answer it

grawji's runtime routes bank writes according to whether `0xD18C` is advertised. Its [bank-enablement guide](https://github.com/p5k369/grawji/blob/7cd98fe/docs/enable-bank-writing.md#L21-L27) assigns the GFX100S, X-Pro3, X100V, and X-T4 to the backup path by assumption, while its [feature matrix](https://github.com/p5k369/grawji/blob/7cd98fe/docs/feature-matrix.md#L90-L93) expects the property path from the X-Pro3 onward. These source documents do not give a settled body classification. A GFX100S reads the unadvertised `D18C`–`D1A5` range; its write pass records the name and 20 of 22 attempted parameters written, two refusals, and persistence of accepted settings [Owner report: GFX100S fw 2.13]. The X100V capture independently confirms selections 1–7 and successful name reads [Captured: FilmKit #1]; a verified film-simulation write remains a published issue report. Those X100V checks do not establish power-cycle persistence. See [the X100V capture](../captures/reproduction.md#x100v-preset-save-capture).

## Common assumptions

### "If `GetDeviceInfo` doesn't list a property, the camera doesn't have it"

Advertisement is not a complete availability test. A GFX100S answers 26 unadvertised codes (including the selector, name, and live `D1A5`), an X-T20 answers a descriptor for an unadvertised `0xD183`, and an unmerged X-T30 II report describes bank reads and writes with an empty advertised-property list. [Owner report: GFX100S and X-T20] [Community: X-T30 II] For details, see [transport](01-transport.md#the-advertised-lists-are-not-complete).

### "`0x201C` means the encoding is wrong"

`0x201C` says the property value is invalid for that request. A wrong encoding and a state-dependent restriction can both produce it; the code alone does not identify the cause. The observed restrictions include ISO, D-Range Priority, film simulation, and bank modes. For the evidence and the unresolved Kelvin-mode comparison, see [Why a write is refused](04-custom-slots.md#why-a-write-is-refused).

### "The magenta–green toning axis is an X-Processor 5 control"

This is false. Fujifilm's manuals document both axes on the X-Pro3, X100V, X-T4, X-S10, X-E4, X-T30 II, GFX100S, and GFX 50S II, and on the GFX100 from firmware 4.00, all X-Processor 4 bodies; a GFX100S also read MG −1 back from its menu. [Published: Fujifilm manuals] [Owner report: GFX100S fw 2.13, menu-confirmed] Only the X-T3, the X-T30, and the GFX100 before firmware 4.00 have one axis. For the encoding, see [Monochromatic Color](03-encodings.md#0xd193--0xd194-monochromatic-color).

### "A bank's settings are not saved until the name is written"

In the final controlled X-T50 tests, USB writes took effect at once and survived bank changes, power cycles, and the camera's **RESET THE CHANGES** with no name written at all. The camera still flagged them with a red dot in **EDIT/SAVE CUSTOM SETTING**. Name writes sent straight after, 10 s later, across a new PTP session, or across a reconnect didn't clear it; the dot was cosmetic in those runs, and a power cycle cleared it while keeping the write. **AUTO UPDATE CUSTOM SETTING** was not recorded. fujifilm-ptp-recipes and fuji-ptp-notes write the settings and then the name; X RAW Studio writes the name first. Both orders appear in successful writes; these observations don't establish a persistence benefit for either order. [Measured: X-T50 fw 1.32, 2026-10-15] [Measured: X-T50 fw 1.32, 2026-10-16; AUTO UPDATE CUSTOM SETTING state not recorded] For details, see [persistence and the red dot](04-custom-slots.md#persistence-and-the-red-dot).

### "The bank block is 24 settings"

It's 23, `0xD18E`–`0xD1A4`. `0xD1A5` is the first of X RAW Studio's optional live writes, carrying `0xD18E`'s value in the captured combined save. Bank-only operations exclude it. [Captured: X-T50 fw 1.31] For details, see [the property reference](02-properties.md#live-shooting-properties).
