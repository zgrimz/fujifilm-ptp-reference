# 8. Methods

How to establish a fact about a Fujifilm body, and the traps that produce false ones. The [descriptor observations](01-transport.md#getdevicepropdesc-is-usually-refused) record refusals for bank properties on the tested bodies, but also working conversion-trigger descriptors on a GFX100S and an X-T20. Try the descriptor for the property and state under test; where it is unavailable, establish the value set by observation.

Record an observation in the [evidence report format](../evidence/report-schema.md): raw values, model, firmware, USB mode, **AUTO UPDATE CUSTOM SETTING** state, the writes attempted, what the read-back showed, and what couldn't be restored. Keep software-only checks and synthetic fixtures labeled apart from camera runs.

## Order of trust

Use this as a starting order for inspecting evidence, with its body, firmware, state, and completeness kept in view:

1. A USB capture of Fujifilm's own software (X RAW Studio). It directly records the exchanges captured in that run, including order, timing, and refusals the client receives. Missing transfers, uncertain UI context, and inferred meanings still limit the conclusions; see [capture provenance and recovery](../captures/reproduction.md#recovery-is-explicit-and-heuristic).
2. A controlled measurement on hardware: one variable changed at a time, with a control.
3. An owner report with raw bytes.
4. A published source — another project's code or notes.
5. Inference.

Before treating a disagreement as an error in a published table, compare the body, firmware, USB mode, bank state, and encoding namespace, and validate the capture or measurement and its interpretation. If those conditions cannot be aligned, record the disagreement as unresolved. A reproducible contradiction under comparable conditions supports a correction at that scope; it does not invalidate a source's results on other bodies. See [errata](errata.md).

## Menu sweep: establishing a value set

To find out what a property holds for each menu setting, use a menu sweep.

1. Select a bank and read every property. This is the baseline.
2. On the camera, change only one menu item for that bank, and record the menu path, whether you saved the change, and the **AUTO UPDATE CUSTOM SETTING** state. On the tested X-T50 fw 1.32, an unsaved shooting-menu Image Size change was readable in the bank block while the camera showed an unsaved-change marker; AUTO UPDATE was not recorded (see [persistence and the red dot](04-custom-slots.md#persistence-and-the-red-dot)). That does not establish the behavior of every menu item or body. The [X-T50 manual](https://fujifilm-dsc.com/en/manual/x-t50/menu_shooting/image_quality_setting/#edit-save_custom_setting) says **ENABLE** saves edits automatically; with **DISABLE**, even edits within **EDIT/SAVE CUSTOM SETTING → EDIT/CHECK** remain marked until saved with **Q** for an individual item or **SAVE THE CHANGES** for all edits. [Published: Fujifilm manuals, X-T50]
3. Read the bank again. A single changed property identifies a candidate mapping. If more than one changes, investigate coupling or other state changes. If none changes, the run hasn't identified the setting's representation; check selection, applicability, save state, and whether the menu change reached that bank.
4. Repeat for every value of that menu item.

The X-T50 menu observations reported in [value encodings](03-encodings.md) establish D-Range Priority (`0xD191`), DR Auto (`0xD190 = 0xFFFF`), the read side of grain, and the identities of `0xD1A3` and `0xD1A4` at their recorded scope. For X RAW Studio's editor, compare the cells changed by each adjustment; a setting can occupy more than one cell. The [X-T50 fw 1.31 and X-T30 fw 2.01 editor walks](../captures/x-rawstudio-editor-walk-xt50-xt30.md) contain single-cell transitions for cells 4, 21, and 22, but the X-T50 white-balance source/mode change alters cells 12 and 15, and its two-axis shift change alters cells 13 and 14. Keep that two-axis change distinguished from a one-axis isolation trial, and inspect the actual differences rather than assuming a one-cell representation.

Record the firmware version: value sets can in principle change with firmware. On the tested X-T50 fw 1.32, the menu was unavailable while connected in **USB RAW CONV./BACKUP RESTORE** mode ([transport observation](01-transport.md#camera-setup)). Each menu step on that setup required unplugging, changing the setting, and replugging, followed by a fresh session and bank selection. Verify whether another body and mode need the same procedure. [`tools/bankprobe.py`](../tools/README.md#bank-research-probe) implements read recovery and bank reselection, with an operator check that the same camera has returned.

## Write probe: establishing what the camera accepts

A menu sweep shows what the camera returns for a menu setting. A write probe shows how it responds to a requested value, and the two can differ: the [grain observations](03-encodings.md#0xd195-grain-effect) distinguish Off read values `6`/`7` from the Off write code `1`, including the tested X-T50 and GFX100S sequences.

1. Save the bank's full contents first.
2. Write each candidate value, read the property back, and record the command outcome (accepted with OK, refused with its response code, or unknown completion) separately from matched, mismatched, or unavailable readback. A match alone doesn't establish that the write caused it; see [client outcomes](11-client-implementation.md#report-command-outcomes-and-state-verification-independently).
3. Interleave a known-good control. Write and verify a value you know the camera accepts before each candidate. Claim normalization only when the transition from that known state demonstrates it; an OK with different readback could also be an ignored write. A successful control helps distinguish a value-specific refusal from a general failure under the tested conditions: DR100 at base ISO served as the control for the DR200/DR400 refusals in the [reported X-T50 fw 1.32 trials](04-custom-slots.md#iso-gating).
4. Restore the bank.

## Render check: establishing what the camera did

For conversion settings, a profile read-back establishes the returned profile value, not the rendered result. Develop a frame with each candidate value, inspect the image, and read its Fujifilm MakerNote, for example with ExifTool. Metadata reports settings recorded in the output; it does not alone establish pixel equivalence or image quality.

In the [reported X-T50 fw 1.32 cell-6 test](05-raw-conversion.md#dynamic-range), `-1` read back as written, but the output was tagged Manual DR100 and had no `AutoDynamicRange` tag. A profile read-back check alone would have missed that difference. This rules out the tested `-1` candidate as DR Auto in that run; no working DR Auto encoding is established here.

### Reading a develop with exiftool

`exiftool -n -FujiFilm:all -InteropIndex -ColorSpace FILE.jpg` prints recognized FujiFilm tags and the standard EXIF color-space fields. `-n` disables print conversion; [ExifTool's value conversion can still apply](https://exiftool.sourceforge.net/under.html), so the output is not necessarily the on-disk representation of every tag.

The table identifies metadata useful for checking conversion settings, by profile cell. Tag IDs and numeric interpretations use [ExifTool 13.55's pinned FujiFilm source](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm) and [standard EXIF InteropIndex definitions](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/Exif.pm#L393-L403) [Published: ExifTool]. Notes marked † use fujifilm-ptp-recipes' [reported X-H2 fw 5.20 isolation shots](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/exif-makernote.md#L154-L183); those original shots are not supplied in the inspected source tree [Published: fujifilm-ptp-recipes]. The two marked ‡ were independently checked in complete EXIF segments from the [public X-T50 and X-T30 previews](../captures/reproduction.md#metadata-is-recoverable-even-when-pixels-are-not) [Captured]. Missing tags remain unknown; an implementation's mapping is not a measurement of every body.

| Cell | Setting | Tag | Read-out |
|--|--|--|--|
| 6 | Dynamic Range | `0x1402` DynamicRangeSetting, `0x1403` DevelopmentDynamicRange, `0x140B` AutoDynamicRange | For `0x1402 = 1` Manual, use `0x1403`; for `0` Auto, use `0x140B`. ExifTool marks `0x1403` valid for manual DR only and also lists historical `0x1402` values for 100%, 230%, 400%, and Film Simulation; preserve those separately ([definitions](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L747-L788)). |
| 7 | D-Range Priority | `0x1443` DRangePriority (0 Auto, 1 Fixed), `0x1444` DRangePriorityAuto (1 Weak, 2 Strong, 3 Plus), `0x1445` DRangePriorityFixed (1 Weak, 2 Strong) | ExifTool's [presence comments](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L842-L859) report `0x1444` only under Auto and `0x1445` only under Fixed on the X-T3; that scope does not establish universal tag presence. HDR Plus = `3` traces to an [X-Pro3 sample-image report](https://exiftool.org/forum/index.php?topic=10799.0). |
| 8 | Film Simulation | `0x1401` FilmMode for the color simulations; `0x1003` Saturation for the monochrome ones (`0x300` B&W, `0x301`–`0x303` with R/Ye/G, `0x310` Sepia, `0x500`–`0x503` ACROS and its filters) | Identify monochrome using [Saturation](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L172-L196); [FilmMode](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L724-L745) has no corresponding monochrome mapping. This does not imply that the FilmMode tag is absent. |
| 9 | Grain | `0x1047` GrainEffectRoughness (0 Off, 32 Weak, 64 Strong), `0x104C` GrainEffectSize (0 Off, 16 Small, 32 Large) | [ExifTool definitions](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L492-L531). |
| 10 | Color Chrome Effect | `0x1048` ColorChromeEffect (0 Off, 32 Weak, 64 Strong) | [ExifTool definition](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L501-L509). |
| 11, 12 | White balance | `0x1002` WhiteBalance; `0x144A`–`0x144C` WBRed/WBGreen/WBBlue | ExifTool [describes the gain fields as white balance as shot](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L874-L878) and gives no DR rule. In the observed X-T50 DR200/DR400 comparisons the gains halved when DR doubled, so compare them at one DR: the same frame developed at DR400 carries 596/302/507 and at DR200 1192/604/1014, and every DR400 output seen carries green 302 against 604 at DR200. [Measured: X-T50 fw 1.32, 2026-09-07 and later develops] |
| 13, 14 | WB shift | `0x100A` WhiteBalanceFineTune | ×20 is reported for the X-H2 † and reproduced in the [X-T50 fw 1.31 and X-T30 fw 2.01 captures](10-jpeg-recipes.md#white-balance-scaling). ExifTool's [newer-camera note](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L225-L231) gives no universal model/firmware discriminator. |
| 16, 17 | Highlight, Shadow Tone | `0x1041` HighlightTone, `0x1040` ShadowTone | −16 per +1 step, sign inverted. With `-n`, ExifTool returns the stored signed value (for example, `−24`); normal output converts it to the dial value and prints an unlabeled half step as `1.5` ([conversion code](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L439-L479)). |
| 21 | Lens Modulation Optimizer | `0x1045` LensModulationOptimizer (0 Off, 1 On) | ‡ |
| 22 | Color Space | standard EXIF `InteropIndex`: R98 sRGB, R03 Adobe RGB | ‡ |
| 23, 26 | Monochromatic Color | `0x1049` BWAdjustment (warm–cool), `0x104B` BWMagentaGreen | [Signed-byte interpretation](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L510-L522): byte `0xEE` (238 unsigned) is −18. |
| 24 | Smooth Skin Effect | `0x104A`, unnamed in the pinned ExifTool table | fujifilm-ptp-recipes [reports 0/32/64 on the X-H2 fw 5.20](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/exif-makernote.md#L156-L169) †; the earlier command does not extract this unknown tag. |
| 25 | Color Chrome FX Blue | `0x104E` ColorChromeFXBlue (0 Off, 32 Weak, 64 Strong) | ExifTool [marks Weak `32` unconfirmed](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L542-L551); fujifilm-ptp-recipes reports that mapping in its X-H2 isolation table †. |
| 27 | Clarity | `0x100F` Clarity | [Published lookup](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L260-L275): ×1000, −5000…5000. |
| 28 (candidate) | Digital Tele-Converter | `0x104D` CropMode (2 Sports Finder, 4 Electronic Shutter 1.25× Crop, 8 Digital Tele-Converter), and the image dimensions | [ExifTool mapping](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L532-L541); cell 28 remains a [candidate identification](06-conversion-profile.md#digital-tele-converter-cell-28--a-candidate). |

The Fujifilm MakerNote might not survive sharing a JPEG; read the file the camera produced. [`tools/jpeg_recipe.py`](../tools/jpeg_recipe.py) reads a documented subset without ExifTool and reports recipe fields and separate observations. Its allowlist excludes Smooth Skin `0x104A` and WB gains `0x144A`–`0x144C`, and it does not validate image dimensions or pixels; see [JPEG recipe extraction](10-jpeg-recipes.md#byte-parsing).

## Capturing Fujifilm's own software

[X RAW Studio](https://www.fujifilm-x.com/global/products/software/x-raw-studio/) is available for Windows and macOS. Capture options are:

- Windows: [Wireshark with USBPcap](https://desowin.org/usbpcap/tour.html). Select the camera's USB root hub, start the capture, do one operation in X RAW Studio, and stop.
- Linux: [usbmon with Wireshark](https://wiki.wireshark.org/CaptureSetup/USB#linux), for software running under Linux; this is general USB-capture guidance, not a claim that X RAW Studio runs natively there.

Save the capture, then decode it with [`tools/ptpcap.py`](../tools/README.md), which reads pcapng and the older pcap that USBPcap writes on its own.

Keep each capture to one operation, such as one bank save or one conversion. Note the body, firmware, and what you did on screen.

### Known capture pitfalls

- USBPcap dropped packets during the [87 MB X-T50 upload](../captures/x-rawstudio-conversion-xt50.md#capture-notes); the decoder recovered the later commands, and the 625/629-byte profiles arrived whole. [Captured: X-T50 fw 1.32, maintainers' capture] Small transfers aren't guaranteed intact: check each container's completeness and retain [recovery diagnostics](../captures/reproduction.md#recovery-is-explicit-and-heuristic).
- The shipped decoder's `--profiles` output requires a complete payload with an integral number of 4-byte cells after `0x1FD`; it skips other lengths, including rawji's reported 632-byte construction with three trailing padding bytes. Missing profile rows therefore do not establish that no profile transfer occurred. Inspect transaction summaries and the [documented profile forms](06-conversion-profile.md#the-host-write-form) before drawing that conclusion.
- Downloaded JPEGs in a capture can have incomplete pixel data. In the [public editor walks](../captures/reproduction.md#metadata-is-recoverable-even-when-pixels-are-not), complete sequential EXIF APP1 segments were recoverable from incomplete transfers. Validate those segment boundaries and parsing before interpreting metadata; that establishes neither intact pixels nor a complete transfer.
- Any capture can include `GetDeviceInfo`, which ends with the body's serial number, and a capture of a conversion also contains your photo. Publish the decoded command stream, not the raw capture.

## Profile harvest: does this body convert?

In the observed runs, `0xD185` becomes readable after a RAF upload. A property sweep before upload therefore cannot establish conversion support. This procedure checks profile availability without rendering:

1. Read `0xD185` (`0x2002` in the observed pre-upload state) and `GetObjectHandles`, as a "before."
2. Upload a RAF that this same body shot, as in [RAW conversion](05-raw-conversion.md#the-sequence) steps 1–2.
3. Run `GetObjectHandles` again to check whether the upload created an object.
4. Read `0xD185`, and record its length, `numParams`, IOPCode, the resolved table base, and the first 64 bytes.
5. Stop. Don't write the profile, trigger, or fetch anything.

Possible outcomes include a readable profile, a refused upload, or an accepted upload followed by an unavailable profile. The inspected profiles resolve at `0x1FD`; retain the bytes and investigate a different layout rather than treating that offset as a capability test. A readable profile establishes profile availability; to test rendering, try a controlled conversion next. For failures, record the failed request, response, USB mode, session state, and RAF provenance before drawing a capability conclusion. `GetDevicePropValue(0xD185)` returned `0x2002` in the observed pre-upload state ([profile-read evidence](02-properties.md#bank-and-conversion-control)). [rawji's README](https://github.com/pinpox/rawji/blob/02cb559/README.md#L31-L38) reports the same code for a foreign RAF without naming the failed request; [grawji's description](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/core.py#L151-L155) places it at `get_profile`, consistent with its [operation order after `send_raf`](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/core.py#L545-L559). [Published: rawji] [Published: grawji] These are published descriptions, not supplied transaction traces. A pre-upload refusal and a post-upload foreign-RAF refusal can therefore come from the same profile-read operation in different states. Neither establishes a refusal of the upload operation itself.

## Persistence check

1. Write a bank.
2. Switch the camera off and on.
3. Read the bank again, and record the **AUTO UPDATE CUSTOM SETTING** state.

The final controlled X-T50 fw 1.32 runs kept USB writes through power cycles and **RESET THE CHANGES**, including runs without a name write. AUTO UPDATE state was unrecorded, and two conflicting earlier results remain unresolved; see [persistence and the red dot](04-custom-slots.md#persistence-and-the-red-dot). The [October records note](../evidence/xt50-october-records.md) separates the executed RESET controls from a case where RESET was grayed out, and changed-value writes from no-ops. Keep those limits with the result and verify persistence on each new target body. Reconnecting USB isn't a power cycle. In the final runs, name writes didn't clear the red dot, while opening the flagged item or power-cycling did. Record which menu screens you opened as well as AUTO UPDATE state, which the [X-T50 manual](https://fujifilm-dsc.com/en/manual/x-t50/menu_shooting/image_quality_setting/#auto_update_custom_setting) says controls automatic saving of body-menu edits; that rule does not establish USB-write persistence under both settings.

## Menu comparison

After decoding a bank, compare every displayed setting against the camera's own menu for that bank. Read-back verification establishes the returned values, not whether the write caused them. It can't prove they mean what the decoder says, because every automatic check agrees with a consistent misreading. A menu mismatch is the most useful thing a new body can produce. One reported exception is a GFX100S fw 2.13 bank at base ISO whose menu showed D-Range Priority **OFF** while `0xD191` held Auto (`0x8000`); see the [owner observation and unresolved follow-up](04-custom-slots.md#the-d-range-priority-interlock).

## Comparing two renders

To compare a conversion over USB with the camera's own conversion of the same frame, examine luminance statistics alongside the images:

- compare the mean, standard deviation, and 1st–99th percentiles;
- measure the signed and absolute per-pixel differences;
- repeat the difference measurements at successive 2× downscales and compare repeated renders of the same settings to establish a noise baseline.

Independent grain renders can differ pixel by pixel and converge under downscaling. Statistical agreement and decreasing differences are consistent with that explanation, but don't prove identical processing or rule out every film simulation or tone-curve difference. Record the comparison method and its limits.

The Fujifilm MakerNote might not survive sharing a JPEG (standard EXIF often does), so when you compare renders sent through messaging apps, don't rely on metadata.

## Traps

- "Not advertised" isn't "absent." Read the property. See [`GetDeviceInfo`](01-transport.md#the-advertised-lists-are-not-complete).
- A read without a bank select describes the parked bank, which might not be any selectable bank.
- Date your evidence. A diagnostic dump can be carried forward and shown in a later report. Check when a sweep was captured, not when the report was exported.
- A pass-through can appear verified even if the write was refused or ignored: the value might already match. Report the returned value and write response separately.
- When identical writes have different outcomes, investigate bank state, including ISO and D-Range Priority, alongside other possible causes. The [reported X-T50 ISO trials](04-custom-slots.md#iso-gating) changed acceptance by changing ISO; the GFX100S comparison in the same section lacks recorded bank ISOs and does not isolate its cause. A correlation with firmware, film simulation, or a bank is a reason for a controlled test, not a diagnosis.
- The camera's menu and the stored value can disagree (D-Range Priority at base ISO). Both can be right.
- One body is one body. Record the model and firmware with every observation, and don't widen a claim to a sensor line or processor generation without saying how many bodies support it.

## Minimum evidence for a new body

In rough order of value and risk:

1. `GetDeviceInfo`, in full.
2. A read-only sweep: `0xD18C`, `0xD18D`, the 23 bank properties and `0xD1A5`, `0xD183`, `0xD185`, and `0x500F`, each with value and descriptor attempts. Don't select a bank yet, and remember this reads the parked bank.
3. The bank count: select upward until refused.
4. Every bank's contents, plus a menu comparison of at least one bank.
5. A grain write probe on one backed-up bank.
6. A full bank write, power cycle, menu comparison, and restore, on a bank the owner can spare.
7. A profile harvest with a RAF the body shot, then one conversion compared against the camera's own.
