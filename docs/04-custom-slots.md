# 4. Custom-setting banks (C1–C*n*)

A body stores *n* custom-setting banks, the camera's C1…C*n*. On bodies with this USB bank interface, `0xD18C` chooses the bank addressed by the name property (`0xD18D`) and setting block (`0xD18E`–`0xD1A4`). The full block has 23 setting codes, but individual bodies can omit properties: an X-S20 refused `0xD198` with `0x200A`. [Published: grawji issue #114] These properties address the bank, not the camera's live shooting state as such: on an X-H2 with C7 selected, the bank's film simulation read ACROS while the live one read PRO Neg. Hi. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]

Here, a bank's working copy means its PTP-visible values, including the unsaved menu edits observed in X-T50 tests. The term describes what was readable, not the camera's internal architecture. When testing, record the **AUTO UPDATE CUSTOM SETTING** state: it wasn't recorded in the working-copy, red-dot, and **RESET** runs. For those observations and their limits, see [persistence and the red dot](#persistence-and-the-red-dot).

`0xD18C` chooses a bank for the host to edit; it isn't the camera's bank switch. In the tests here, writing it didn't change which bank the camera shot with. No shooting-bank switch is characterized in this property path; that isn't a claim about every USB operation or the settings-backup path. On a GFX100RF the selector keeps whatever was last written to it across a closed session and a cable reconnect, and then reports that value rather than the bank the body is on; until a host writes it, and again after a bank change on the body, it reads the body's bank. [Published: GFX100RF, fuji-ptp-notes] An X-T50 keeps it both across a cable reconnect and through a bank change on the body: with the body switched to C6, `0xD18C` still read `7` and an unselected read of `0xD192` answered C7's film simulation. [Measured: X-T50 fw 1.32, 2026-10-15] The GFX100RF's reset doesn't happen on that body. So a read of `0xD18C` tells you where the last host left the selector, not necessarily what the camera is using, and a name written without a fresh select lands on whichever bank that is.

`0xD1A5`, the code after the block, isn't a bank setting: the captured combined save sends it first on the optional live-copy branch, with `0xD18E`'s value. The bank-only sequence later in this chapter excludes it; see [the property reference](02-properties.md#live-shooting-properties).

## How many banks

Probe the count by selecting banks in ascending order until a select is refused.

| Body | Banks | Evidence |
|--|--|--|
| X-T50 | 7 | [Measured] |
| GFX100S | 6 — selecting 7 answers `0x200A` | [Owner report: fw 2.13] |
| X-M5 | 4 — selecting 5, 6, or 7 fails | [Published: FilmKit issue #18, fw 1.30] |
| X-S20 | 4 over the `0xD18C` block; whether the camera refuses a select of 5–7 isn't shown (one refusal came from the tool's own guard) | [Published: fujicli] [Published: grawji issue #114] |
| X-S10 | C1–C4 read over USB, with values that differ per bank; no select of 5 is reported, so the USB count isn't proven. C1–C4 on the mode dial, per the manual | [Published: X-S10, Filmcase] [Published: Fujifilm manuals] |
| GFX100 II | C1–C6 on the mode dial; in USB tether mode `0xD18C` answers a descriptor with enumeration `1`–`6` | [Published: Fujifilm manuals] [Published: libgphoto2 camera dump, paraphrased] |
| X-H2 | 7 — all read, written, and named in a seven-bank bench | [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| X-T5 | 7 — C1–C7 read and written | [Published: X-T5 fw 4.20, fujifilm-ptp-recipes] [Published: fujicli] |
| X-E5 | 7 — `0xD18C` refuses `8` and above | [Published: grawji] |
| GFX100RF | 7 | [Published: fuji-ptp-notes] |
| X-T30 II | 7 — C1–C7 read, written, and named at fw 2.04 | [Community: a report in fujifilm-ptp-recipes' unmerged pull request #2] |
| X100V | 7 — banks 1–7 selected and their names read in the preset-save capture; the manual gives seven | [Published: FilmKit issues #1 and #8] [Captured: FilmKit #1 preset-save capture; see [capture reproduction](../captures/reproduction.md#x100v-preset-save-capture)] [Published: Fujifilm manuals] |
| X-Pro3 | fails so far — reads, writes, and name writes all fail at fw 2.00; the response codes aren't recorded, and the source hasn't diagnosed it. The manual gives seven | [Published: fujifilm-ptp-recipes] [Published: Fujifilm manuals] |
| X-T20, X-H1, X-T3, X-T30, X100VI | 7, per the manuals' **EDIT/SAVE CUSTOM SETTING** pages; see [bank counts from Fujifilm's manuals](07-cameras.md#bank-counts-from-fujifilms-manuals) | [Published: Fujifilm manuals] |

The manual's count and the USB count agree on every body that has both: seven on the X-T50, X-H2, X-T5, X-E5, X100V, X-T30 II, and GFX100RF, six on the GFX100S, and four on the X-M5. The X-S20's manual also gives four, but its USB sources' C5–C7 rejection came from application validation, so its USB count isn't established. [Published: Fujifilm manuals]

No clearing operation is characterized in this bank-property path. The camera's menu can **ERASE** a bank and **CREATE NEW** ones [Published: Fujifilm manuals, X-T50]. A property snapshot restores readable values, not a proven empty/occupied state; it doesn't establish what the separate settings-backup path can restore. What an erased bank reads over USB is untested.

Bodies without the block might still have banks. grawji reports that the X100F and X-T3 lack the preset properties and writes their banks by downloading the settings backup object, patching the bank records inside it, and restoring it. Its routing checks advertised properties; the inspected material supplies no direct X100F selector-refusal trace, so it doesn't establish what an unadvertised `0xD18C` would answer on that body. Its X-T3 layout reports checksum validation on restore; its X100F layout declares no whole-file checksum. [Published: grawji] These body-specific paths are described under [backup and restore](01-transport.md#settings-backup-and-restore); they aren't characterized here. The [advertised-property comparison](01-transport.md#the-advertised-lists-are-not-complete) records separate failed-selector reports for the X-T3.

## Reading a bank

1. Read `0xD18C` and keep the value, so you can put the selection back afterward.
2. To select bank C*k*, call `SetDevicePropValue(0xD18C, k)`.
3. Optional: To confirm the select took, read `0xD18C` back.
4. Read `0xD18D` and each of `0xD18E`…`0xD1A4` (~2–4 ms each on an X-T50).
5. When you finish, select the original value again.

If you read without selecting, you get whatever bank the selector last pointed at, which isn't necessarily the body's bank and might not be any bank you can select. On an X-T50, it's the last value written over USB, kept across reconnects and the body's own bank changes. [Measured: X-T50 fw 1.32, 2026-10-15] A GFX100S read without a select returned `0xD18E = 16` and `0xD18F = 1` on firmware 1.32. After the owner updated to firmware 2.13, every one of its six selectable banks read `14` and `2`. [Owner report: GFX100S, separate fw 1.32 and 2.13 sessions] Firmware changed between the sessions, so this comparison doesn't isolate the effect of selecting a bank.

X RAW Studio reads `0xD18D`, then `0xD18E`…`0xD1A4` in mostly ascending order (`0xD199`, `0xD19C`, `0xD19A`, `0xD19B` in that order). It never reads `0xD1A5`. [Captured]

Settling after a select: in the X-T50 save, X RAW Studio starts the name command 4.676 ms after the selector command starts, only 0.385 ms after its response. That save has no substantial settling pause; see [timing](01-transport.md#timing). [Captured: X-T50 fw 1.31, FilmKit #12] fujifilm-ptp-recipes recommends waiting about 100 ms after the select before reading, and found 50 ms clean across a seven-bank bench on an X-H2; it doesn't report a failure without the delay, so this is a precaution rather than a measured need. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] It also re-reads `GetDeviceInfo` after each select on its write path; X RAW Studio doesn't. FilmKit waits 100 ms after each select, with no failure reported without it [Published: FilmKit]; fujicli selects and writes with no delay and no read-back on an X-T5 [Published: fujicli].

On a GFX100S every bank answers every property, including banks nobody has programmed, so an "empty" bank looks like any other. [Owner report] Whether other bodies report an unprogrammed bank differently is an [open question](open-questions.md).

## Writing a bank

### The sequence

This bank-only sequence follows the order captured from X RAW Studio on an X-T50, plus a dependency rule for turning D-Range Priority off. The captured save didn't exercise changing that priority successfully. [Captured: X RAW Studio on X-T50 fw 1.31] [Measured: X-T50 fw 1.32]

1. Select the bank: `SetDevicePropValue(0xD18C, k)`. In the captured X-T50 save, the name command follows the selector response by 0.385 ms, without a substantial settling pause; another body might need one.
2. Write the name, `0xD18D`. Several X-T50 setting writes persisted without a name write, and the red dot didn't reliably indicate persistence. See [the tested persistence behavior](#persistence-and-the-red-dot).
3. After checking the complete write set and preserving recoverable originals ([client implementation](11-client-implementation.md)), write only the intended settings in ascending order, `0xD18E` → `0xD1A4`. A bank-only writer stops there; X RAW Studio's optional live copy, `0xD1A5` first, is a separate branch (see [the property reference](02-properties.md#live-shooting-properties)). The exceptions to ascending order:
   - `0xD19C` (Kelvin) immediately after `0xD199` (White Balance mode), and the shifts `0xD19A`/`0xD19B` after it. [Captured] [Published: FilmKit] On an X-S10 a Kelvin write sent after the shifts zeroed them [Published: X-S10, Filmcase], so the order isn't cosmetic there.
   - `0xD191` (D-Range Priority) before `0xD190` (Dynamic Range) whenever the write turns the priority off. While the priority is on, the camera refuses `0xD190`, so a write that turns it off and sets a dynamic range must clear it first. [Measured: X-T50 fw 1.32] [Owner report: GFX100S fw 2.13]
4. Read every property back and compare by meaning. See [Verifying a write](#verifying-a-write).

Film simulation before tones and color: fuji-ptp-notes states, with no run described, that a GFX100RF resets its tone and color settings when the film simulation changes, silently undoing anything written before it. [Published: GFX100RF, fuji-ptp-notes] An X-T50 menu sweep of the film simulation moved no other property, but its tones might have been at 0 [Measured: X-T50 fw 1.32, 2026-10-15], so the question is open. X RAW Studio's ascending order already puts `0xD192` ahead of every tone and color property, and both peers write it first by rule.

In the captured combined save, X RAW Studio attempts all 23 bank settings, then the optional live mirror, and continues past refusals. On that capture, the camera refused `0xD191`, `0xD193`, `0xD194`, and `0xD19C`, all with `0x201C`. [Captured] fujifilm-ptp-recipes' static analysis describes this failure handling for settings other than Image Size. Image Size has a fallback: a refused bank write to `0xD18E` can be followed by `0xD1A8`, while a refused live write to `0xD1A5` can be followed by `0xD03A` and `0xD03B`. The bank fallback sends only the size component; the live fallback sends both size and aspect ratio. This fallback wasn't exercised in the captured save, and no body has been shown to trigger it here. See [Image Size](03-encodings.md#0xd18e-image-size). [Published: fujifilm-ptp-recipes, static analysis] For the ordinary state-dependent refusals, a tool can record each failure and continue, or skip the writes the next section shows the camera refuses in its current state.

### Writes that are only valid in some states

| Property | Write only when | Otherwise |
|--|--|--|
| `0xD19C` Kelvin | Select `0xD199 = 0x8007` (Color temperature), following the published writer guidance | FilmKit reports this prerequisite from its X100VI captures. The X-T50 capture refused Kelvin `0` under Daylight, so it doesn't isolate a mode restriction from an invalid value. fujifilm-ptp-recipes applies this bank-writer rule but measures the refusal on live `0xD017`; fuji-ptp-notes states the rule without a measured basis. See [Kelvin evidence](03-encodings.md#0xd19c-color-temperature). [Captured] [Published: FilmKit] [Published: fujifilm-ptp-recipes] [Published: fuji-ptp-notes — unmarked rule] |
| `0xD193`/`0xD194` Monochromatic Color | Film simulation is a monochrome type with toning (not Sepia), and the value is a multiple of 10 within the body's menu range ×10 (±180 on the X-T50; ±90 where the menu stops at 9) | `0x201C` on color simulations [Captured] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]; `0x201C` on Sepia [Measured: X-T50 fw 1.32, 2026-10-15]; `0x201C` off the 10-step grid [Measured: X-T50 fw 1.32, 2026-10-15] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] and beyond ±180 [Measured: X-T50 fw 1.32, 2026-10-15]. fuji-ptp-notes also reports refusal on color simulations and of `0` even on monochrome, in a community-marked README row and its later [experiment log](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/EXPERIMENTS.md#L34-L35), without response codes, an identified simulation for the zero test, or a detailed transaction trace. [Published: fuji-ptp-notes] The X-T50 and X-H2 accept `0`; FilmKit's code reports refusal on an X100VI. |
| `0xD19F` Color | Film simulation isn't monochrome | `0x201C` [Measured: X-T50]. FilmKit omits Color writes on monochrome simulations; its code supplies no numeric refusal. [Published: FilmKit, writer policy] |
| `0xD190` Dynamic Range, `0xD19D`/`0xD19E` tones | D-Range Priority is Off | `0x201C` [Measured: X-T50] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]. fuji-ptp-notes reports tone-write refusal on a GFX100RF without a property-specific numeric response. [Published: GFX100RF, fuji-ptp-notes — tones] |
| `0xD1A2` Clarity | The bank's file format is JPEG on the tested X-T50 | `0x201C` for all tested HEIF-bank values, including the held one; a JPEG bank accepts in the same session. [Measured: X-T50 fw 1.32, 2026-10-15] The GFX100RF source reports the narrower HEIF/JPEG format comparison, without identifying bank versus live format. [Published: GFX100RF, fuji-ptp-notes] |

### Persistence and the red dot

On the tested X-T50 fw 1.32, USB-written bank settings persisted without a name write or separate commit command. The final controlled runs kept the value through **RESET THE CHANGES** and power cycling. The red dot did not indicate that the USB write was unsaved. These runs did not record the **AUTO UPDATE CUSTOM SETTING** state. Two earlier X-T50 results conflict with them and remain unexplained: an early `working-copy` run saw **RESET THE CHANGES** revert a bare USB write, and an earlier measurement lost settings written without a name after a power cycle [Measured: X-T50]; see [open questions](open-questions.md#bank-protocol).

The X-T50 manual says **ENABLE** applies a body change to the current bank at once; **DISABLE** marks it with a red dot until you save it by hand. [Published: Fujifilm manuals, X-T50] The [manual coverage paragraph](07-cameras.md#auto-update-custom-setting-in-the-menus) records other bodies documenting the same behavior and the pages read that don't mention the item. [Published: Fujifilm manuals]

With **ENABLE**, a change the body makes while shooting on a bank lands in that bank, so a host that wrote a bank and later relies on it reads it back rather than assuming it still holds what was written. [Inferred: from Fujifilm's manuals]

On a GFX100RF, fuji-ptp-notes reports that an enabled setting also makes a live USB write land in the shown bank, while a disabled setting doesn't. [Published: GFX100RF, fuji-ptp-notes] Those menu and live-write rules are distinct from the tested bank-property results that follow; this record does not establish their behavior under both AUTO UPDATE settings.

The X-T50 fw 1.32 observations were:

- Unsaved menu edits were readable. An Image Size changed in the shooting menu on C7, without saving, read back as C7's `0xD18E` with the body on C7 and on C6. The camera marked C7 as holding unsaved changes. [Measured: X-T50 fw 1.32, 2026-10-16; AUTO UPDATE state not recorded]
- USB writes took effect immediately. A film simulation written to the active bank showed in the Q menu before any bank change, and the camera used it. After switching to another bank and back, both the Q menu and USB read-back still showed it. [Measured: X-T50 fw 1.32, 2026-10-16]
- Name writes didn't clear the flag in the final controlled tests. Property writes left a red dot on the item in **EDIT/SAVE CUSTOM SETTING**, none in the Q menu, and offered **SAVE THE CHANGES** and **RESET THE CHANGES**. The dot remained when the name was written immediately, 10 seconds later, after CloseSession/OpenSession, and after unplugging and replugging the cable. [Measured: X-T50 fw 1.32, 2026-10-16]
- Five instructed power-cycle/readback cases kept a changed film-simulation value. Three had no name write and two wrote the name afterward, including fresh-session cases with the session closed or the cable pulled. The transcripts direct the operator to switch off, wait five seconds, and switch on before continuing; this is operator-mediated evidence, not instrumented power detection. [Measured: X-T50 fw 1.32, 2026-10-15] [Measured: X-T50 fw 1.32, 2026-10-16] In the name-last test, the film simulation and name both survived. [Measured: X-T50 fw 1.32, 2026-10-15]
- The final `reset-check` run's two changed-value controls kept the USB write through **RESET THE CHANGES**, with and without a name write, under instructions not to open the changed item. The operator reports RESET was performed; the responses do not independently confirm every requested navigation restriction. Other RESET runs aren't controls: in one, RESET was grayed out, and the others rewrote a value the bank already held. **RESET THE CHANGES** did revert an edit made in the camera's shooting menu. [Measured: X-T50 fw 1.32, 2026-10-16; AUTO UPDATE state not recorded]
- Other actions cleared the flag. Opening the flagged item in **EDIT/CHECK** and backing out without changing it cleared the dot and grayed out **SAVE THE CHANGES** and **RESET THE CHANGES**. A power cycle also cleared the dot and kept the written value in one run. [Measured: X-T50 fw 1.32, 2026-10-16; AUTO UPDATE state not recorded]

The final controlled `name-timing`, `reset-check`, and `power-dot` runs establish the practical result on this X-T50: the red dot is cosmetic for the tested USB writes, which survive **RESET THE CHANGES** and power cycling. Name writes didn't clear it; opening the flagged item and backing out, or power cycling, did. The results suggest USB writes land in the bank itself, with shooting-menu edits in a separate layer that **RESET** discards. [Inferred] The internal storage interpretation remains conditional on the unrecorded AUTO UPDATE state.

Both peer records describe successful name-last writes: fujifilm-ptp-recipes on an X-H2 and X-T5, and fuji-ptp-notes on a GFX100RF. [Published: fujifilm-ptp-recipes] [Published: fuji-ptp-notes] The captured X RAW Studio sequence earlier in this chapter writes the name first. These observations don't establish a persistence benefit for either order.

The runs behind these results are published as [sanitized packages](../evidence/README.md#available-x-t50-packages); the [October records note](../evidence/xt50-october-records.md) gives the source-array position of each write and read. The probe's prompts mention AUTO UPDATE as an instruction, not as a recorded observation of that setting.

## Why a write is refused

`0x201C` means the property exists but the camera won't take this value now. The table includes observed refusals, source-reported conditions, and manual-based predictions. A source that reports a refusal without a numeric response doesn't establish `0x201C`; those gaps and the inferred conditions are identified in the following table.

| Cause | Refused | Evidence |
|--|--|--|
| Kelvin `0` while Daylight is selected; cause not isolated | `0xD19C` | [Captured: X-T50] The public captures provide no valid-value comparison under a non-Kelvin mode. FilmKit reports a mode prerequisite from its X100VI captures; the peers' bank-writer rules aren't additional bank-refusal measurements, and the fujifilm-ptp-recipes refusal is on live `0xD017`. See [Kelvin evidence](03-encodings.md#0xd19c-color-temperature). |
| Color film simulation | `0xD193`, `0xD194` | [Captured] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] [Published: fuji-ptp-notes — a community-marked README row and later experiment-log assertion, without a numeric response or detailed trace] |
| Monochromatic Color value not a multiple of 10 | `0xD193`, `0xD194` | [Measured: X-T50 fw 1.32, 2026-10-15] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| Monochromatic Color value beyond ±180 | `0xD193`, `0xD194` | [Measured: X-T50 fw 1.32, 2026-10-15] |
| Monochromatic Color value `0`, even on a monochrome simulation | `0xD193`, `0xD194` on a GFX100RF (fuji-ptp-notes' community-marked README row and later experiment-log assertion) and on an X100VI (FilmKit's code); neither source supplies a numeric response or detailed transaction trace for zero refusal. Accepted on an X-T50 and an X-H2 | [Published: fuji-ptp-notes] [Published: FilmKit] [Measured: X-T50 fw 1.32, 2026-10-15] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| Monochrome film simulation | `0xD19F`, even a write of its current value — and only `0xD19F`: Color Chrome Effect, Color Chrome FX Blue, and both white balance shifts take writes under ACROS | [Measured: X-T50 fw 1.32, 2026-10-03] [Measured: X-T50 fw 1.32, 2026-10-15] |
| Sepia | `0xD193`, `0xD194`, every tested value | [Measured: X-T50 fw 1.32, 2026-10-15] |
| Bank's ISO below 2× base | `0xD190` = DR200 | [Measured: X-T50] |
| Bank's ISO below 4× base | `0xD190` = DR400 | [Measured: X-T50] |
| Bank at base ISO | `0xD191`, any value, even the one it already holds | [Measured: X-T50] |
| D-Range Priority on in the bank | `0xD190`, `0xD19D`, `0xD19E` — exactly these three | [Measured: X-T50 fw 1.32, 2026-09-18] [Published: X-H2 fw 5.20, fujifilm-ptp-recipes — the same three, by a controlled pair of runs] |
| Bank's file format is HEIF (a bank setting outside the 23) | `0xD1A2` Clarity, every tested value | [Measured: X-T50 fw 1.32, 2026-10-15] The separate GFX100RF report establishes a camera-format gate, not this bank-specific comparison. |
| Bank's file format is HEIF | `0xD1A4 = 2`, presumably: the X-T50 and X-E5 manuals say HEIF forces **COLOR SPACE** to sRGB | [Inferred: from Fujifilm's manuals] |
| Sports Finder Mode on in the bank, by correlation | `0xD18E` Image Size, including a write of its current value | [Measured: X-T50 fw 1.32, 2026-09-06 and 2026-09-15: the refusing banks had Sports Finder Mode on; no on/off comparison on one bank] |
| Digital Tele-Converter ON/OFF menu prompts on C7 | `0xD18E = 7` receives `0x201C` after ON and `0x2001` after OFF; both read back the already-held `7` | [Measured: X-T50 fw 1.32, 2026-10-15, operator-mediated comparison; [sanitized run](../evidence/xt50-20261015-232441/README.md)]. Setup is prompted, without independent mode readback or a magnification-specific result. |
| The CH-burst 1.29× crop on in the bank | `0xD18E`, presumably: the manual limits Image Size to M under it, as under Sports Finder Mode | [Inferred: from Fujifilm's manuals] |
| HDR on in the bank | No Image Size lock established; the October 15 HDR step was skipped | No supporting USB result; slight cropping in the manuals does not establish a write refusal. [Published: Fujifilm manuals] |
| No lens attached | `0xD1A3` Lens Modulation Optimizer; body and numeric response unspecified | [Published: fujicli code comment — reports a PTP error] |
| The body doesn't take writes to it | `0xD1A5` on a GFX100S, even a write of its current value | [Owner report] |
| Bank selected on a body whose banks fail over this block | everything, on an X-Pro3 fw 2.00; the response codes aren't recorded | [Published: fujifilm-ptp-recipes] |

Three consequences:

- A no-op write can fail. In several of these states, the camera refuses a write of the value a bank already holds. Unless you're prepared for the refusal, don't write a setting you aren't changing.
- The camera can accept identical bytes on one bank and refuse them on another. Bank-specific ISO, D-Range Priority, and JPEG/HEIF state can affect writes, and some of that state isn't among the 23 readable properties. A refusal alone does not identify which condition caused it.
- A refusal and an out-of-range value look the same. `0x201C` is also what an off-grid Monochromatic Color value gets, so you can mistake a locked property for an unsupported one. Before concluding that a tone dial is missing, check `0xD191`. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]

fujifilm-ptp-recipes also skips Color Chrome Effect, Color Chrome FX Blue, and both white balance shifts on monochrome simulations, as a writer policy. The camera doesn't refuse them: under ACROS, an X-T50 took a changed value on all four and refused only Color. [Measured: X-T50 fw 1.32, 2026-10-15] Two sources disagree on whether Sepia also locks Color: grawji says the camera grays it out and skips the write, while fujicli's rules allow it [Published: grawji] [Published: fujicli]; untested here.

### ISO gating

The manuals give the thresholds as absolute ISO numbers, which equal 2× base for DR200 and 4× base for DR400 on every body checked (X-T50: 250 and 500), and cap both at ISO 12800, the top of the standard range. [Published: Fujifilm manuals] The floors per body, as the manuals print them: the D-Range Priority Weak and Strong floors equal the DR200 and DR400 floors on every body whose menu has the item except the X-E5, whose Weak floor is printed as ISO 320 against a DR200 floor of 250, and an upper bound appears only where the manual states one. [Published: Fujifilm manuals]

| Bodies | DR200 and Weak | DR400 and Strong | Upper bound | **D RANGE PRIORITY** in the menu |
|--|--|--|--|--|
| [X-T20](https://fujifilm-dsc.com/en/manual/x-t20/menu_shooting/image_quality_setting/index.html) | 400 | 800 | not stated | no |
| [X-H1](https://fujifilm-dsc.com/en/manual/x-h1/menu_shooting/image_quality_setting/index.html) | 400 | 800 | 12800 | yes |
| [X-T3](https://fujifilm-dsc.com/en-int/manual/x-t3/menu_shooting/image_quality_setting/index.html), [X-T30](https://fujifilm-dsc.com/en-int/manual/x-t30/menu_shooting/image_quality_setting/index.html), [X-Pro3](https://fujifilm-dsc.com/en-int/manual/x-pro3/menu_shooting/image_quality_setting/index.html), [X100V](https://fujifilm-dsc.com/en-int/manual/x100v/menu_shooting/image_quality_setting/index.html), [X-S10](https://fujifilm-dsc.com/en-int/manual/x-s10/menu_shooting/image_quality_setting/), [X-T30 II](https://fujifilm-dsc.com/en/manual/x-t30-2/menu_shooting/image_quality_setting/), [X-S20](https://fujifilm-dsc.com/en-int/manual/x-s20/menu_shooting/image_quality_setting/), [X-M5](https://fujifilm-dsc.com/en-int/manual/x-m5/menu_shooting/image_quality_setting/) | 320 | 640 | 12800 | yes |
| [X-T5](https://fujifilm-dsc.com/en-int/manual/x-t5/menu_shooting/image_quality_setting/), [X-H2](https://fujifilm-dsc.com/en-int/manual/x-h2/menu_shooting/image_quality_setting/), [X-T50](https://fujifilm-dsc.com/en-int/manual/x-t50/menu_shooting/image_quality_setting/), [X100VI](https://fujifilm-dsc.com/en/manual/x100vi/menu_shooting/image_quality_setting/) | 250 | 500 | 12800 | yes |
| [X-E5](https://fujifilm-dsc.com/en/manual/x-e5/menu_shooting/image_quality_setting/) | 250; Weak 320 | 500 | 12800 | yes |
| [GFX100S](https://fujifilm-dsc.com/en-int/manual/gfx100s/menu_shooting/image_quality_setting/) | 200 | 400 | 12800 | yes |
| [GFX100 II](https://fujifilm-dsc.com/en/manual/gfx100ii/menu_shooting/image_quality_setting/), [GFX100RF](https://fujifilm-dsc.com/en/manual/gfx100rf/menu_shooting/image_quality_setting/) | 160 | 320 | 12800 | yes |

These are menu statements. The only USB test of a floor here is the X-T50 measurement that follows; the GFX100S and X-S10 observations later in this section are the other USB evidence.

Measured on one X-T50 bank with D-Range Priority off, changing only the bank's ISO between runs: [Measured: X-T50 fw 1.32, base ISO 125, 2026-09-17]

```
ISO 125 (base)   DR100 accepted   DR Auto accepted   DR200 0x201C     DR400 0x201C
ISO 250          DR100 accepted   DR Auto accepted   DR200 accepted   DR400 0x201C
ISO 500          DR100 accepted   DR Auto accepted   DR200 accepted   DR400 accepted
```

DR100 at base ISO is the control: it shows the property still takes writes there, so the refusals are about the values. The thresholds are exactly 2× and 4× base. [Measured: X-T50 fw 1.32, 2026-10-15] Whether a bank at an extended ISO (the X-T50's L 64–100 or H 25600–51200) refuses DR200 and DR400, as the manual's cap predicts, is untested.

The gate follows the bank's ISO in the X-T50 tests. A GFX100S accepted the same DR400 write on C2 and refused it on C3 and C4. All three initially held DR100 and D-Range Priority Off, but their monochromatic-color and grain values differed. The supplied transaction reports do not record their ISO values, so this comparison demonstrates a difference between banks without isolating its cause. [Owner report: GFX100S fw 2.13, 2026-09-17] An X-S10 (base ISO 160) refused DR400 `0x201C` with its bank at ISO 250 and accepted it at ISO 800, and at base ISO refused both `0xD191` and DR400: independent support for the ISO gate, consistent with 4× base without isolating that threshold, and a second body for the base-ISO lock on `0xD191` described later. [Published: X-S10, Filmcase — firmware unstated]

No bank-ISO read is characterized through the tested X-T50 properties. `0x500F` ExposureIndex answers `0x200A` on banks at ISO 125 and ISO 500 alike. [Measured: X-T50 fw 1.32, 2026-09-18] A refusal can reveal a gate, but doesn't identify the bank's ISO or rule out another cause. The GFX100S advertises `0x500F`; whether it tracks the selected bank is untested.

D-Range Priority (`0xD191`) is gated harder: at base ISO, the camera refuses every write, including one of the value already held, and at ISO 500 every write succeeds. [Measured: X-T50 fw 1.32] The manuals give Weak a floor of 2× base and Strong 4× base, both capped at 12800 (the X-E5 manual alone gives Weak a floor of ISO 320; the per-body floors are in the table earlier in this section) [Published: Fujifilm manuals], so at ISO 250 you'd expect an X-T50 to take Weak and refuse Strong; untested.

D-Range Priority also drives **TONE CURVE** and **DYNAMIC RANGE** itself whenever it's anything but **OFF**, in the manual's own words [Published: Fujifilm manuals, X-T50], which is the interlock described in the next section.

### The D-Range Priority interlock

D-Range Priority is a highlight-and-shadow curve that the camera drives itself. While it's on, the camera refuses writes to Dynamic Range, Highlight Tone, and Shadow Tone, and nothing else. Measured with a bank at ISO 500 and the priority set to Strong in the camera's menu, writing a recipe that set every field: [Measured: X-T50 fw 1.32, 2026-09-18]

```
0xD19D Highlight Tone   0x201C
0xD19E Shadow Tone      0x201C
0xD190 Dynamic Range    (not attempted — known to be locked)
everything else         written and verified
```

The X-H2 bank-property account reports the same three, from a controlled pair of runs: with the priority on Auto, the camera refused the three, and with it Off, it accepted the same values. It also reports `0xD190 = 0xFFFF` while the priority is on and interprets it as a placeholder, without supplying the numeric Off baseline. The source's separate live-property account explicitly reports an Auto/Off comparison confirming both the live interlock and live DR `65535`. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] On an X-T50, `0xFFFF` is menu-confirmed DR Auto, and a bank holding DR100 keeps reading `100` after the priority is set to Strong in the menu. [Measured: X-T50 fw 1.32, 2026-10-15] That X-T50 result doesn't disprove the X-H2 report; keep the bank and live namespaces, and the two bodies, separate (see [Dynamic Range](03-encodings.md#0xd190-dynamic-range)). A GFX100RF refuses the tones while the priority is on. [Published: GFX100RF, fuji-ptp-notes]

So:

- When turning the priority off, write `0xD191` before `0xD190`. The same order holds on a GFX100S. [Owner report: GFX100S fw 2.13, 2026-09-18, menu-confirmed 2026-09-29] fujifilm-ptp-recipes' writer rule is to omit the three while the priority is anything but Off, or to write `0xD191 = 0` first, write them, and restore the priority afterward. [Published: fujifilm-ptp-recipes, writer rule]
- If the camera refuses the `0xD191` write itself (for example, at base ISO), the priority stays as it was. Send the three dependent writes anyway and report each outcome: they land if the priority was already off and are refused if it wasn't. [Inferred: from fujifilm-ptp-recipes' X-H2 interlock observations]
- In the tested base-ISO states, `0xD191` didn't permit changing the bank's priority, including turning it off. This doesn't establish what another USB path might allow.

The stored value and the menu can disagree at base ISO. On a GFX100S, C1 and C2 both held `0xD191 = 0x8000` byte for byte. The camera's own menu showed C2 as **AUTO** and C1 as **OFF**; C1's bank was at base ISO and C2's at ISO 800. At base ISO, the body acts as if the priority is off and grays the item out, while the bank keeps storing what it held. [Owner report: GFX100S fw 2.13, 2026-09-18] Before treating a lone D-Range Priority mismatch as a decode error, check it against the bank's ISO.

One GFX100S observation doesn't fit cleanly yet. After the owner reported raising C1 to ISO 800, a write to `0xD191` was refused again. [Owner report: GFX100S fw 2.13] Either the change didn't save to that bank, or the ISO isn't the only gate on that body. See [open questions](open-questions.md).

## Values a bank remembers while they are inactive

Several settings keep a stored value while another setting makes them irrelevant, as the camera's own menus do:

| Setting | Kept while | Evidence |
|--|--|--|
| Grain size | Grain is Off — read back as `6` (Small) or `7` (Large) | [Measured: X-T50] [Owner report: GFX100S] |
| Kelvin (`0xD19C`) | White balance isn't Kelvin | [Measured: X-T50 fw 1.32, 2026-09-20] |
| White balance shift, per mode (`0xD19A`/`0xD19B`) | Another white balance mode is active — each mode keeps its own shift, and the pair reports the active mode's | [Measured: X-T50 fw 1.32, 2026-10-15] |
| Monochromatic Color (`0xD193`/`0xD194`) | The simulation is color or Sepia | [Measured: X-T50, 2026-09-20] |
| Color (`0xD19F`) | The simulation is monochrome | [Measured: X-T50, 2026-10-03] |
| Dynamic Range and tones | D-Range Priority is on | [Measured: X-T50] |

When presenting a recipe, don't show inactive values as applied settings: showing a Kelvin for an Auto-WB bank invents a setting the user can't see. Preserve their raw values in a recovery snapshot. Most can't be written while inactive, so restoration must account for whether the experiment changed them before restoring the final mode; see [Restoring a bank](#restoring-a-bank).

## Verifying a write

- Read every written property back. An OK response doesn't prove the camera kept the value.
- Compare by meaning, not bytes, for anything the camera normalizes. Grain Off written as `1` and read as `6`/`7` is a success.
- Read `0xD18C` back after selecting. The selection decides where every later write lands. A select that answered OK but didn't move would send every following write to the wrong bank, with all read-backs agreeing.
- Don't treat a matching read-back as proof that an unchanged value was written. If a tool writes back a value it has just read from the bank (to preserve a setting it doesn't edit), a later read can match even if the write was refused or ignored. Report the returned value and write response separately, not just "verified".
- Prove persistence by power-cycling the camera and reading the bank again, with the **AUTO UPDATE CUSTOM SETTING** state recorded. A name write or red dot isn't a persistence test; see [the X-T50 persistence results](#persistence-and-the-red-dot).
- Prove the decoding by comparing against the camera's own menu. Read-back establishes the returned bytes, not whether the write caused them or whether they mean what the decoder says.
- Don't rely on a read-back to tell a bank setting from a global one. On the X-T3, X-T30, X-H1, and, the source says, the X-Trans III bodies generally, the white balance shift is reported to be stored once per white balance mode rather than per bank, so a shift written to one bank reads back correctly and has changed every bank using that mode. fujifilm-ptp-recipes ties per-bank storage to a `CustomSetting` flag in X RAW Studio's capability table that is absent below the X-Pro3, as an inference. [Community: owner reports collected by fujifilm-ptp-recipes, not measured over USB in the cited sources] [Published: fujifilm-ptp-recipes, static analysis, inferred] An X-T30 II is reported to keep its shifts per bank. [Community: fujifilm-ptp-recipes PR #2] None of the older bodies has shown a bank protocol over this block here, so this is a caution for whichever body first does.

## Restoring a bank

Restoring is a write and follows every rule earlier in this chapter, with three additions:

- Decide the conditional writes from the saved bytes, but put a changed inactive value back before restoring the state that makes it inactive. Skip `0xD193`/`0xD194` unless the saved simulation is a monochrome type with toning, and `0xD19C` unless the saved white balance is `0x8007`: a restore that wrote all three while inactive reported three refusals. [Measured: X-T50 fw 1.32, 2026-09-14] If the experiment changed one of them, write it while its prerequisite still holds, then restore the final simulation or white balance and shifts, and verify against the baseline; if that isn't possible, report what wasn't restored.
- Direct writes of grain Off's saved `6`/`7` bytes are refused on the tested X-T50 and GFX100S. Both bodies demonstrated reconstruction of `6` by writing `2` then `1`, and of `7` by writing `5` then `1`. A GFX100S rollback that wrote only `1` restored Off but changed saved `6` to `7`. Use the [demonstrated grain sequences](03-encodings.md#0xd195-grain-effect) where applicable and verify the saved size as well as Off; those sequences alone don't prove complete-bank restoration. [Measured: X-T50 fw 1.32, 2026-09-14] [Owner report: GFX100S fw 2.13, 2026-09-15]
- Order D-Range Priority by direction. If the saved bank had the priority off, turn it off before writing Dynamic Range and the tones. If it had the priority on and the bank currently has it off, write Dynamic Range and the tones first and turn the priority on last. An ascending-order restore had `0xD190 = 400` refused before `0xD191 = Off` was accepted. [Measured: X-T50 fw 1.32, 2026-10-03]

Save the bank's name along with its settings. Otherwise, you can end up restoring settings under the name a later write left behind.

One whole-bank rollback has been checked byte for byte. An X-T50 bank held Classic Chrome with grain Off (`7`, Large remembered), white balance Auto, a dormant Kelvin of 10000, and inactive toning of `180`/`−180`. A test write replaced its name and 19 settings in ascending order. On a later connection, a restore wrote the saved name and the same 19 settings in ascending order, with grain as `5` → `1`. Neither write touched `0xD191`, `0xD193`, `0xD194`, or `0xD19C`, so they kept their saved values: the test left D-Range Priority unchanged, and toning and Kelvin are conditional writes in that state. Every write answered OK. The restore's read-back, and a scan of every bank afterward, matched the saved baseline in all 23 bank settings and the name, including grain `7`. This is one bank in one state. It doesn't cover a restore that has to change D-Range Priority, write Kelvin, or put back toning, and it isn't a persistence test. [Measured: X-T50 fw 1.32, 2026-10-18]

## Bodies with a Film Simulation dial

On bodies with a physical Film Simulation dial, the dial overrides the bank's film simulation unless it's set to **C**. The `0xD192` write succeeds either way. [Measured: X-T50] Bodies with a dial: X-T50, X-E5, X-T30 III, and X-M5; their manuals' parts pages place the dial and state the override at **C**. [Published: Fujifilm manuals] The dial also has **FS1**–**FS3** positions, assigned in **FILM SIMULATION DIAL SETTING**, and on the X-E5 and X-T30 III, an **FS RECIPE** item stores image-quality settings per FS position: a second recipe store outside C1–C7. These registered settings apply when **FS RECIPE** is **ON**; on the X-T30 III, setting the auto mode selector lever to **AUTO** prevents them from applying even when **FS RECIPE** is **ON**. [Published: Fujifilm manuals] On an X-E5, `0xD18C` refuses `8` and above, so the bank block doesn't reach those positions; grawji reaches them through the settings backup. [Published: grawji]

A bank's film simulation has also been seen to change between sessions with no host connected. On an X-T50, C2's `0xD192` went from ASTIA (`0x03`) to PRO Neg. Hi (`0x04`) across a power cycle and a bank change made in the camera's own menu. Every other property on every bank was byte-identical. The cause wasn't established. [Measured: X-T50 fw 1.32, 2026-09-06] The working-copy behavior described earlier is the likely cause: a film simulation changed on the body while it was on C2 shows up in C2's block without a save. [Inferred]
