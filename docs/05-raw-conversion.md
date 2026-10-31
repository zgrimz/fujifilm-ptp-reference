# 5. In-camera RAW conversion

The camera can develop a RAF file with its own image processor and hand back the JPEG. This is what Fujifilm's X RAW Studio does: the computer uploads the RAF, adjusts a conversion profile, and triggers the conversion. The sequence in this chapter changes the conversion profile without writing custom-setting banks.

## Prerequisites

- The camera's USB setting is **USB RAW CONV./BACKUP RESTORE**.
- This body shot the RAF. rawji [reports a foreign-RAF failure with `0x2002`](https://github.com/pinpox/rawji/blob/02cb559/README.md#L38), without naming the failed PTP request. grawji [places that error at the profile read after sending the foreign RAF](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/core.py#L151-L155), so an upload response alone doesn't establish that the file can be converted. [Published: rawji] [Published: grawji] One owner-reported observation fits that placement, with its cause inferred: an X-M5 answered OK to `0x900C` and `0x900D` for a 2,186,314-byte upload that carried the RAF signature but whose header, by the client's log, named no body it could check against, and `0x2002` to the `0xD185` read that followed. The file was most likely not an X-M5 RAF, and its size leaves open whether it was a complete RAF at all, so a payload that isn't a usable RAF is a second candidate cause of `0x2002` at that step; the body didn't refuse it at the upload. See [the X-M5](07-cameras.md#x-m5). [Owner report: X-M5 fw 1.30, 2026-10-31, the client's log] [Inferred] The container matters: grawji converts another body's raw data by embedding it in an uncompressed RAF the connected body shot. [Published: grawji]
- The body supports conversion. For the bodies known to support it, see [Camera bodies](07-cameras.md).
- The battery can last the job. Fujifilm says the camera's power saving feature does not work while it's connected in USB RAW CONVERSION mode and that conversion uses the camera's battery, whose level X RAW Studio shows [Published: Fujifilm, X RAW Studio Features & Users Guide]; in the public captures it polls [`0xD36A`/`0xD36B`](02-properties.md#live-shooting-properties) about every 3 s [Captured: X-T50 fw 1.31, X-T30 fw 2.01]. No conversion failing for want of charge is recorded here.

## The sequence

| Step | Operation | Detail | Evidence |
|--|--|--|--|
| 1 | `SendObjectInfo` `0x900C`, params `[0, 0, 0]` | An ObjectInfo dataset: StorageID `0`, ObjectFormat `0xF802` (RAF), ObjectCompressedSize = file size, Filename `FUP_FILE.dat`, all other fields zero, and empty date and keyword strings. | [Published: FilmKit] [Measured: X-T50] [Captured] |
| 2 | `SendObject2` `0x900D` | The RAF bytes as the data phase. | [Published: FilmKit] [Measured: X-T50] |
| 3 | `GetDevicePropValue(0xD185)` | The conversion profile, now describing the RAF's as-shot settings. 625 bytes on an X-T50. | [Measured: X-T50] |
| 4 | — | Patch only the cells you mean to change; leave every other byte alone. | see later in this chapter |
| 5 | `SetDevicePropValue(0xD185)` | The patched profile, in the host-write form (629 bytes). For observed tail values and header differences, see [the conversion profile](06-conversion-profile.md#the-host-write-form). The FilmKit log also records successful conversion from a modified profile retaining the 625-byte read form on an X-T50 fw 1.31; the fw 1.32 commenter's successful conversions do not specify write length. | [Captured] [Published: libfuji captures] [Published: FilmKit issue #12 log — 625-byte writes] |
| 6 | `GetDevicePropValue(0xD185)` | Re-read and compare the patched cells before triggering. | Client recommendation — see later in this chapter |
| 7 | `SetDevicePropValue(0xD183, n)` | Trigger: `1` = full resolution, `0` = reduced-size render. The camera refuses `2` with `0x201C`. | [Published: FilmKit #15] [Captured] [Measured: X-T50] |
| 8 | Poll for completion | Either the `0xD212` event list or `GetObjectHandles`. See the following section. | [Captured] [Measured: X-T50] |
| 9 | `GetObjectHandles` → `GetObjectInfo` → `GetObject` | Find the new object, check its ObjectInfo (see [the converted object](#the-converted-object)), and download the JPEG. Validate the returned format and byte count, then save the output before cleanup. | [Captured] [Measured: X-T50]; validation and durable saving are client recommendations |
| 10 | `DeleteObject` `0x100B` | Remove only the identified conversion output after successful validation and saving. | [Captured] [Measured: X-T50]; cleanup condition is a client recommendation |

Use the name `FUP_FILE.dat`. X RAW Studio uploads under that name [Captured], and so do FilmKit, rawji, and libfuji [Published: FilmKit, rawji, libfuji]. Whether the camera accepts any other name is untested here.

On a GFX100S, `GetObjectHandles` returned zero handles both before and after a 208,071,296-byte upload (198.43 MiB); the uploaded RAF wasn't enumerated as a card object in that run. [Owner report: GFX100S fw 2.13, 2026-09-17] An X-T50 did the same: the list was empty after each of two 87 MB uploads in one session. Its conversion outputs got handle `2` after the first upload, `4` after the second, and `5` and `6` for two more conversions of the second upload. [Measured: X-T50 fw 1.32, 2026-10-18] Each upload apparently takes a handle number without being listed. [Inferred]

`GetObjectHandles` parameters: StorageID `0xFFFFFFFF` (all), ObjectFormat `0` (any), Parent `0`. A pre-upload enumeration can check whether uploading creates an object. For identifying conversion output, take a fresh validated baseline after upload and profile preparation, immediately before triggering. Delete only the object this conversion produced; see [client implementation](11-client-implementation.md#develop-a-raf-without-confusing-another-object-for-the-result).

rawji (and grawji through it), FilmKit, fujicli, and fxraw take the first handle `GetObjectHandles` lists after the trigger, with no list taken before it [Published: rawji [`fuji_usb.py`](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L562-L567); FilmKit [`session.ts`](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/session.ts#L625-L630); fujicli [`manager.rs`](https://github.com/karaolidis/fujicli/blob/177671c/crates/fujicore/src/features/render/manager.rs#L52-L70); fxraw [`fuji.rs`](https://github.com/tkcranny/fxraw/blob/90f5b5bdc674d5fc5fc59b0ef883a538f8be1acd/src/fuji.rs#L468-L506)], and rawji, FilmKit, and fxraw carry on when `DeleteObject` is refused [Published: rawji [L595–600](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L595-L600); FilmKit [L648–653](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/session.ts#L648-L653); fxraw [L499–504](https://github.com/tkcranny/fxraw/blob/90f5b5bdc674d5fc5fc59b0ef883a538f8be1acd/src/fuji.rs#L499-L504)]. An output left behind by a refused delete, or by a conversion that completed after its client gave up, would be returned as the next job's result. [Inferred; no such run is recorded] A listed handle need not be a live object either: in USB tether shooting, an X-T3 keeps listing a downloaded image and refuses `GetObjectInfo` for it with `0x200F`, and a GFX 50R did the same for a handle just deleted; see [response codes](01-transport.md#response-codes). [Published: libgphoto2 commit 47b539b; gphoto2 issue #456 logs]

### Completion

| Method | Signal | Evidence |
|--|--|--|
| Poll `0xD212`, the camera's event list | `0000` (no events) while converting; one event for `0xD20E` (`0100 0ED2` + a u32 value) when the JPEG is ready | [Captured: X RAW Studio on X-T50 fw 1.32] [Published: libfuji, libgphoto2 — event-list structure] |
| Poll `GetObjectHandles` | A new handle appears | [Measured: X-T50] |

Both work. `0xD212` is the cheaper signal and is what Fujifilm's own software uses. Parse it as an event list rather than matching bytes: other events could appear in it.

The public X-T50 fw 1.31 capture also returns a `0xD20E` event after object deletion. [Captured: FilmKit #12 capture] Interpret it in the current operation's context and identify the output against the pre-trigger baseline; an event alone does not identify the new conversion object. Its 32-bit event value also does not establish the native type of property `0xD20E`; see the [property reference](02-properties.md#bank-and-conversion-control).

### Output

| Trigger | Output | Evidence |
|--|--|--|
| `0xD183 = 1` | Full-resolution JPEG: ~6.5 MB from X RAW Studio on one X-T50 frame and 26.4–26.8 MB on another (the toning conversions); 25.7 MB from another host | [Captured: X-T50 fw 1.32, 2026-09-07 and 2026-10-17] [Measured: X-T50 fw 1.32, 2026-10-18] |
| `0xD183 = 0` | Reduced-size JPEG: ~1.1 MB and 4.4–4.7 MB from X RAW Studio on two X-T50 frames; ~4 MB from FilmKit's renders on an X-T50; half the linear size (3120×2080 from 6240×4160) on an X-M5 | [Captured] [Published: FilmKit issue #12 log and #15, X-T50] [Published: FilmKit issue #18, X-M5 fw 1.30] |

File size follows the frame and its settings far more than the host: X RAW Studio's own full-resolution outputs range from ~6.5 MB to 26.8 MB across two X-T50 frames. No same-frame, same-profile comparison across hosts has been recorded.

Profile cell 2 (file type) requests the output format: `0x7` JPEG, `0x9` 8-bit TIFF, `0xB` 16-bit TIFF, `0x12` HEIF. [Published: rawji] [Published: fujifilm-ptp-recipes, static analysis] On an X-T50, `11` gives a 16-bit TIFF of about 233 MB, and only with `0xD183 = 1`. [Published: FilmKit issue #15] A body might ignore a requested TIFF or HEIF format and return JPEG; inspect the returned container, as [rawji's output handling](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/__main__.py#L426-L436) does. [Published: grawji, [export handling](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/controllers/exports.py#L220-L221)] grawji reports 10-bit HEIF output. Its [format-capability matrix](https://github.com/p5k369/grawji/blob/7cd98fe/docs/feature-matrix.md#L12-L17) assumes current firmware and uses in-camera capabilities from the manuals and its capability database as a proxy for USB support; many rows have not been verified over USB. [Published: grawji]

rawji's fast preview requests only the result's thumbnail with `GetThumb` (`0x100A`), but [falls back to full `GetObject`](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L571-L587) if that request fails or returns no data. rawji describes the speed-up on a 40 MP body and names no body for the 640×480 JPEG of about 40 KB; grawji reports that size on an X-E5. [Published: rawji, [thumbnail implementation](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L535-L542)] [Published: grawji, [X-E5 preview](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/core.py#L606-L612)]

On a GFX100S, the full conversion came out 5824×4368, the same size as a conversion done on the camera itself from its own menu. [Owner report: GFX100S fw 2.13, 2026-09-29]

### The converted object

`GetObjectInfo` on the new handle returns a complete standard dataset. In the three X RAW Studio toning captures it is 114 bytes every time: StorageID `0x10000001`, ObjectFormat `0x3801` (EXIF/JPEG), ProtectionStatus `0`, and four strings that end exactly at the end of the dataset: a filename of the form `DSCF0006.jpg`, a capture date, and empty modification-date and keyword strings. X RAW Studio requests it three times per object before downloading. For each capture's final conversion, ObjectCompressedSize equals both the declared length of the `GetObject` data phase and the size of the JPEG X RAW Studio saved: 26,835,053, 26,625,646, and 26,446,458 bytes. The previews' sizes match their declared download lengths the same way. [Captured: X-T50 fw 1.32, 2026-10-17 toning captures] [Measured: X-T50 fw 1.32, 2026-10-17, saved files] The captures hold only the first 66,520 bytes of each download, so the equality is between declared sizes and saved files, not a count of captured image bytes; see the [transcript's capture notes](../captures/x-rawstudio-toning-xt50.md#capture-notes).

Separately, four conversions through ImageCaptureCore on iOS, one full-resolution and three reduced, were recorded as returning 114-byte datasets with the same StorageID, ObjectFormat, and ProtectionStatus, and a 12-character filename starting `DSCF`. Each time, ObjectCompressedSize equaled the bytes downloaded, 25,714,890 for the full-resolution JPEG. [Measured: X-T50 fw 1.32, iOS 27.0.1, 2026-10-18] A client can check a candidate's format and declared size before downloading, compare the received byte count afterward, and identify the output before deleting it; see [client implementation](11-client-implementation.md#develop-a-raf-without-confusing-another-object-for-the-result).

### When a conversion doesn't complete

No stuck conversion is recorded here: none of the retained traces or decoded captures holds a `0x2019`, and all 13 conversion triggers in the retained client traces and reports were accepted and produced an output after one to three `GetObjectHandles` polls. [Measured: X-T50 fw 1.32, 2026-09-14 to 2026-10-19] An X-M5 at firmware 1.20 answered `0x2019` to two develop attempts in one session, with no earlier conversion through that client recorded; the report holds no transactions from that session and the cause wasn't recorded, so it neither confirms nor contradicts the account below. See [the X-M5](07-cameras.md#x-m5). [Owner report: X-M5 fw 1.20, 2026-10-25, the client's develop records] The rest of this section comes from other projects and from users of X RAW Studio.

- **Symptom.** grawji treats a conversion whose output hasn't appeared within 30 s, or any later command answered `0x2019`, as a wedged body that retrying can't recover. [Published: grawji, [`camera_info.py`](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/camera_info.py#L73-L80)] Its [test fixtures](https://github.com/p5k369/grawji/blob/7cd98fe/tests/camera/test_camera_info.py#L88-L91) place the `0x2019` on the next trigger; they are fixtures, not captured answers. rawji's [batch loop](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/__main__.py#L416-L424) ends at the first timeout, and its comment there says retrying makes it worse. grawji's author contributed that advice, so the two are one source. [Published: rawji]
- **Recovery.** The sources report only a power cycle. grawji tells the user to [remove the battery briefly](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/views/window.py#L1762-L1768) if the camera won't switch off. [Published: grawji] X RAW Studio users report the same: an X100V on fw 3.01 hung, with the application, while opening RAFs shot on that firmware, and couldn't be switched off until its battery was removed [Community: X100V fw 3.01, X RAW Studio 1.20.0.0 on macOS, 2023]; an X-S10 whose green light kept flashing while the application reported waiting for the camera needed the battery out too, and its reporter later traced the hang to a RAF carrying a metadata tag the software didn't know [Community: X-S10, 2021]. Allow a long reconnect window afterward; see [platform notes](09-platform-notes.md#disconnection).
- **Untried.** No source reports a USB-level recovery from a stuck conversion. The [class requests on endpoint 0](01-transport.md#class-requests-on-endpoint-0) are the candidate. grawji's only reset is pyusb's USB device reset, run [when opening fails](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/core.py#L534-L539), before its one retry; its comment says opening is safe to retry because no conversion is in flight. That is a bus reset, not the class Device Reset request. [Published: grawji]
- **Wait limits differ.** rawji, grawji through it, and FilmKit, whose session code is a rawji port, wait 30 s: rawji [polls `GetObjectHandles` every 50 ms](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L535-L606) and FilmKit [every second](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/session.ts#L610-L664); fxraw makes [45 polls 2 s apart](https://github.com/tkcranny/fxraw/blob/90f5b5bdc674d5fc5fc59b0ef883a538f8be1acd/src/fuji.rs#L457-L519); fujicli has [no limit, polling every 100 ms](https://github.com/karaolidis/fujicli/blob/177671c/crates/fujicore/src/features/render/manager.rs#L47-L73). rawji and FilmKit end the wait at the first poll that isn't `0x2001`; fxraw keeps polling through errors. [Published: rawji, FilmKit, fxraw, fujicli] No trigger-to-output time is recorded here, and a 16-bit TIFF (about 233 MB on an X-T50) or a GFX frame may take longer than a JPEG. [Inferred] A body still converting when a client's wait runs out might answer `0x2019` without being wedged; nothing here distinguishes the two. [Inferred]
- **Don't trigger again** after a timeout. A late output can also be mistaken for the next job's; see [client implementation](11-client-implementation.md#develop-a-raf-without-confusing-another-object-for-the-result).

## Upload once, develop many

The conversion buffer survives a conversion. To render several versions of one photo, upload it once and repeat steps 4–10 for each version. [Measured: X-T50] [Published: grawji, which renders live previews this way] A conversion that never completes can leave the body unresponsive and answering `0x2019`; see [when a conversion doesn't complete](#when-a-conversion-doesnt-complete).

In the captured X-T50 conversion, re-reading `0xD185` after conversion returned the last written cell values. [Captured] This isn't established as a universal echo rule: the sequence and provenance of libfuji's `xt5_*` files are undocumented, and one apparent pair changes cell 4 between write and read. [Published: libfuji; interpretation conditional on file order] So patch each version from the profile read at step 3. Patching the latest re-read would build each version on top of the one before.

X RAW Studio itself converts three times for one job: an as-shot preview when the user opens the file (`0xD183 = 0`), a recipe preview when the user chooses a preset (`0`), and the final full-resolution conversion (`1`). It re-reads `0xD185` after each. [Captured: X-T50 fw 1.32, 2026-09-07]

## Verify the profile before triggering

After an OK response to `SetDevicePropValue(0xD185)`, re-read the property and compare the patched cells before triggering. This is a defensive check of the camera's returned state; an OK response alone is not a comparison of that state with the intended values. A matching read-back still does not establish how the conversion engine will render them.

On an X-T50, the same profile bytes produced a heavy green cast on one conversion and a correct render on later ones. [Measured: X-T50, 2026-08-23] The profile bytes alone do not explain the different outcomes. A trigger arriving before a profile change took effect is one hypothesis. [Inferred] No write/readback mismatch trace or controlled timing experiment is available here to establish that mechanism. Re-reading can detect a mismatch in returned cells, but this anecdote does not establish that readback prevents the green cast.

Treat green output as a symptom with more than one possible cause. The available evidence does not isolate a white-balance failure, a profile timing issue, or another cause in this case.

## Dynamic range

| Write to cell 6 | Result | Evidence |
|--|--|--|
| The frame's own DR, or lower | Clean render at that DR. X RAW Studio wrote 200 onto a DR400 frame, and the returned JPEG's metadata reports `DevelopmentDynamicRange: 200`. | [Measured: X-T50 fw 1.32, by eye, 2026-09-07] [Captured: X-T50 fw 1.32, 2026-09-07; [transcript](../captures/x-rawstudio-conversion-xt50.md#what-it-shows)] |
| Higher than the frame was shot at, in the tested cases | Accepted, and the JPEG's EXIF reports the higher DR, but the render has a heavy green cast. The cause of the cast was not isolated. | [Measured: X-T50 fw 1.32, by eye, 2026-09-07] |
| `-1` (the bank's DR Auto value) | Accepted and stored as `-1`, then rendered at DR100: not Auto, and not the frame's own DR200. The output is tagged Manual, carries no `AutoDynamicRange`, and matches the DR100 control's Fujifilm tags. The sampled mean absolute pixel difference was 0.43, the closest reported comparison; no second DR100 control established the noise floor, so this isn't exact pixel equality. | [Measured: X-T50 fw 1.32, 2026-09-07; MakerNotes re-read 2026-10-17] |

[libfuji's comment](https://github.com/petabyt/libfuji/blob/a3bd237/fp/src/d185.c#L131-L134) says to select only the original DR or lower, and [fujicli enforces that restriction](https://github.com/karaolidis/fujicli/blob/177671c/fml/camera.cue#L459-L478) in its client rules. Those sources do not independently establish the X-T50 response, EXIF, or green-cast mechanism. [Published: libfuji and fujicli — comment and implementation rule] [FilmKit issue #17](https://github.com/eggricesoy/filmkit/issues/17) reports green tint when requesting DR400 for a low-ISO shot, without identifying the body, as-shot DR, PTP response, or output EXIF. It supports that narrower symptom report. [Published: FilmKit #17]

For a client:

- The X-T50 accepted the tested higher-DR requests. As a precaution, cap a requested DR at the frame's as-shot DR, which is in cell 6 of the profile read at step 3.
- No working DR Auto encoding is established here. The inspected non-HDR X RAW Studio conversions use 100, 200, or 400. [Captured] Published HDR encodings are a separate case. To approximate Auto, consider that the camera's own DR Auto never chose above DR200 on three high-contrast frames shot at ISO 640+ [Measured: X-T50, 2026-09-07], and that the [X-T50 manual](https://fujifilm-dsc.com/en/manual/x-t50/menu_shooting/image_quality_setting/#dynamic_range) says **DR AUTO** chooses only DR100 or DR200 [Published: Fujifilm manuals]. Using DR200, capped at the as-shot value, reproduces what X RAW Studio wrote for the captured DR400 file. This heuristic has not been shown to reproduce DR Auto's scene-dependent choice across photos.
- The as-shot DR isn't a safe stand-in for Auto. A frame's as-shot DR400 might be a manual setting from whatever the camera was set to when it was shot.

To check what a conversion actually rendered, read the output JPEG's Fujifilm MakerNote with exiftool: `DynamicRangeSetting` (`0x1402`) says whether the render was Auto or Manual; for a Manual render, `DevelopmentDynamicRange` (`0x1403`) holds the DR, and for an Auto render the DR the camera chose is in `AutoDynamicRange` (`0x140B`) instead, since ExifTool marks `0x1403` as valid only for manual DR. [Published: ExifTool] The profile read-back only proves the camera stored a value, not what it did with it. See [reading a develop with exiftool](08-methods.md#reading-a-develop-with-exiftool).

## White balance

Cells 11 and 12 decide white balance together:

| Cell 11 | Cell 12 | Result |
|--|--|--|
| `1` | `0` | Use the RAF's as-shot white balance |
| `2` | a white balance mode (same values as `0xD199`) | Use that mode; for `0x8007`, the Kelvin value is in cell 15 |

[Published: libfuji captures — as-shot on an X-H1; a 2200 K Kelvin conversion on an X-Pro3] [Measured: X-T50]

The observed and published cases use the bank WB codes through this pair; no exhaustive mode-by-body matrix has been established here. White balance shifts (cells 13 and 14) are stored directly (+4 is `4`, −5 is `−5`) with a supported range of ±9 in the tested X-T50 cases. The camera ignored a tested out-of-range value, leaving no shift; that isn't clamping to the endpoint. [Measured: X-T50] fujicli and grawji differ in their handling of shifts under as-shot white balance (cell 11 = `1`): fujicli treats them as inert and writes `0`, while grawji writes them. In its [transplanted Auto-WB explanation](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/transplant/embed.py#L18-L31), grawji says the engine starts from the RAF's stored G/R/B multiplier triple and adds the recipe shifts. That explanation does not establish shift behavior for every as-shot mode or body; the general question remains untested here. [Published: fujicli] [Published: grawji]

## Matching X RAW Studio

Seventeen bank/profile pairs had identical raw values in the captured X-T50 conversion. This supports the mapping but doesn't distinguish direct copying from independent serialization or establish behavior under other settings and bodies. [Captured: X-T50 fw 1.32, 2026-09-07] For the mapping, see [the conversion profile](06-conversion-profile.md#bank-properties-and-profile-cells). Two consequences:

- For grain Off the captured write is `7`, matching the bank's read-side value. fujifilm-ptp-recipes' static analysis finds a second serializer in X RAW Studio that itself produces `7` for Off with size Large, so the `7` might be built rather than copied; a conversion from a bank with grain Off and size Small (which would copy as `6`) would tell. [Published: fujifilm-ptp-recipes, static analysis] Whether the converter also treats the write-side `1` as Off in a profile is untested on the X-T50; rawji reports it works on an X-E5. [Published: rawji]
- The bank's Kelvin value and cell 15 match even when white balance is Auto. Whether that value affects an Auto develop is untested here.

## Proving a conversion matches the camera's own

On a GFX100S, the owner developed the same RAF over USB and on the camera itself with the recipe set by hand. [Owner report: GFX100S fw 2.13, 2026-09-29] The two JPEGs are a close statistical match, measured on the originals. Both decode to 5824×4368; their 8-bit luminance means (90.96045 and 90.96171) and standard deviations (48.56310 and 48.56495) agree to two decimal places, and all 1st–99th integer percentiles match. The signed mean difference is 0.0013 levels, while the mean absolute difference is 7.56 levels. With exact area averages at 2×, 4×, 8×, and 16× downscales, the absolute difference falls to 5.02, 2.78, 1.47, and 0.75 levels: approximately halving at the coarser scales, not at every step.

This supports closely matched overall tone and is consistent with separate grain renders. [Inferred] It does not establish pixel identity, every recipe setting, or grain as the sole cause of the differences. The shared files retain matching standard capture metadata but no Fujifilm recipe MakerNotes; the route each image came from is the owner's attribution. See [Methods](08-methods.md#comparing-two-renders).
