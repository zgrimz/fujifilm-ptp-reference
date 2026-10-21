# 1. Transport and session

## Camera setup

Set the camera's USB connection setting to **USB RAW CONV./BACKUP RESTORE** (the exact menu wording varies slightly by body). This is the mode Fujifilm's X RAW Studio uses for the procedures here. [Measured: X-T50] [Owner report: GFX100S] It isn't the only mode exposing banks on every body: the GFX100RF answers bank writes in tether mode, and the GFX100 II has a bank-selector descriptor there. [Published: fuji-ptp-notes] [Published: libgphoto2 camera dump, paraphrased] Check conversion support and property visibility for each body and mode.

In any other mode, the camera still answers PTP, but describes itself very differently. To identify the mode, see [Recognizing the wrong USB mode](#recognizing-the-wrong-usb-mode).

The camera's own menu is unavailable while it's connected in this mode. The X-T50 shows only its USB screen, so reaching the menu means unplugging the cable; every menu-sweep step is therefore a disconnect and a reconnect, after which the next command needs a fresh `OpenSession` and a new bank select. The disconnect loses nothing on the camera, and the bank selector keeps its value across the reconnect. [Measured: X-T50 fw 1.32, 2026-10-15] A host that guides a menu sweep must expect the camera to vanish and return at each step, rather than report the camera as unresponsive.

## PTP framing

The protocol is standard PTP (ISO 15740 / PIMA 15740) over USB bulk endpoints, with Fujifilm vendor operations and properties. All integers are little-endian. The container layout and byte order are specified in the [USB Still Image Capture Device Definition 1.0](https://www.usb.org/document-library/still-image-capture-device-definition-10-and-errata-16-mar-2007), §7.1 and Annex A.

```
Container:  [u32 length][u16 type][u16 code][u32 transactionID][payload…]
Types:      1 Command   2 Data   3 Response   4 Event
Command:    payload = up to five u32 parameters
Response:   code = response code; payload = up to five u32 parameters
```

A transaction is a command, an optional data phase (in either direction), and a response. Before anything else except `GetDeviceInfo`, open a session (`0x1002`). Keep transactions strictly sequential: one in flight at a time. See PIMA 15740:2000, §§9.2–9.3.

Strings use the PTP string format: one byte holding the character count (including the terminating NUL), then that many UCS-2LE code units, the last of which is `0x0000`. An empty string is a single `0x00` byte in PIMA 15740:2000, §5.3.4; an X-T50's unnamed bank answers its name as three bytes (a count of `1` and the NUL), and `0xD20B` answers the same on an X-T50 and an X-T3. [Published: FilmKit issue #12 and #5 logs]

For hosts that enumerate by USB identification: the vendor ID is `0x04CB`; FilmKit's constants and issue logs list X-T3 `0x02DD`, X-T30 `0x02E3`, X100V `0x02E5`, X100VI `0x0305`, and X-T50 `0x0306`. An X-M5 showed `0x030C` in one report and `0x030D` in another, so the product ID might change with the USB mode. [Published: FilmKit and its issues #7, #18] For the X-T4, [libgphoto2's supported-device table](https://github.com/gphoto/libgphoto2/blob/92171a3/camlibs/ptp2/library.c#L2742) and [grawji's camera-ID table](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/camera_info.py#L37-L39) give `0x02E6`. [FilmKit's constants](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/constants.ts#L149) and [rawji's enum](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_enums.py#L521) instead give `0x02E7`, neither with a cited X-T4 observation; grawji's table notes that no source backs rawji's value. `0x02E7` is unverified; no mode-specific test here resolves the disagreement. [Published: FilmKit, rawji, libgphoto2, grawji]

## Operations

| Code                | Name                       | Used for                                        | Evidence                                |
| ------------------- | -------------------------- | ----------------------------------------------- | --------------------------------------- |
| `0x1001`            | GetDeviceInfo              | What the body is and what it speaks             | standard                                |
| `0x1002` / `0x1003` | OpenSession / CloseSession |                                                 | standard                                |
| `0x1007`            | GetObjectHandles           | Finding the converted JPEG                      | standard                                |
| `0x1008`            | GetObjectInfo              |                                                 | standard                                |
| `0x1009`            | GetObject                  | Downloading the converted JPEG                  | standard                                |
| `0x100B`            | DeleteObject               | Removing the converted JPEG afterward           | standard                                |
| `0x1014`            | GetDevicePropDesc          | Property descriptors — often refused; see [`GetDevicePropDesc` is usually refused](#getdevicepropdesc-is-usually-refused) | standard                                |
| `0x1015`            | GetDevicePropValue         | Every read in this record                       | standard                                |
| `0x1016`            | SetDevicePropValue         | Every write in this record                      | standard                                |
| `0x900C`            | SendObjectInfo (Fujifilm)  | First half of the RAF upload                    | [Published: FilmKit] [Captured]         |
| `0x900D`            | SendObject2 (Fujifilm)     | Second half of the RAF upload                   | [Published: FilmKit] [Captured]         |
| `0x901D` | SendObject (Fujifilm) | A second vendor upload operation, which libfuji describes as similar to `0x900D`. The X-T50 and X-T20 advertise it; nothing in this record uses it. | [Published: libfuji] [Measured: X-T50] [Owner report: X-T20] |

The X-T20 also advertises `0x9801`, `0x9802`, `0x9803`, and `0x9805`, the MTP object-property operations. [Owner report: X-T20 fw 2.01, USB diagnostics] No body has been seen to need them for anything in this record.

## Response codes

Fujifilm bodies use a small set of codes, and two of them mean different things in different places.

| Code | Name | What it means from a Fujifilm body |
|--|--|--|
| `0x2001` | OK | Accepted. For a write, this does not prove the camera kept the value — read it back. |
| `0x2002` | General Error | Used for several unrelated situations; the code alone doesn't establish that an operation is unsupported. Examples: every `GetDevicePropDesc` on an X-T50 preset property (an X-H2 answers an empty data phase and then `0x2002` for every property, standard ones included [Published: X-H2 fw 5.20, fujifilm-ptp-recipes]; an X100VI likewise for every advertised property [Published: libgphoto2 camera dump]; a GFX100RF in **USB RAW CONV.** mode answers `0x2002` while values read fine [Published: GFX100RF, fuji-ptp-notes]); reading `0xD185` before a RAF has been uploaded; reading `0xD183` on an X-T50 before an upload; reading the profile after sending a RAF the body didn't shoot [Published: grawji]. rawji also reports a foreign-RAF failure with this code but doesn't identify the failed request; see [RAW conversion](05-raw-conversion.md#prerequisites). fuji-ptp-notes calls this code InvalidObjectHandle, which is `0x2009`'s name. |
| `0x200A` | DeviceProp Not Supported | The requested property operation isn't supported in the current context. A descriptor refusal doesn't establish that the value is unavailable: the GFX100S answers `GetDevicePropDesc` this way for every preset property while values read fine. It also answers this way when selecting a bank number it doesn't have; an X-S20 returns it for `0xD198 = 1`, the unsupported Smooth Skin property on its tested bank path [Published: grawji issue #114]. |
| `0x200F` | Access Denied | grawji reports this when `GetObject` and `SendObject` share one settings-backup session (body unspecified in that statement), and when an X-T3 restore carries a stale checksum. For the distinct body scopes, see [backup and restore](#settings-backup-and-restore). [Published: grawji] |
| `0x2015` | No Valid ObjectInfo | A malformed RAF upload: answered to a malformed `SendObject` on an X-T50. [Measured: X-T50] Separately, [FilmKit's upload code](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/session.ts#L474-L491) warns that ObjectFormat `0x5000` instead of `0xF802` causes silent failure; the comment identifies neither the tested body nor a response code. FilmKit identifies its upload implementation as a rawji port, and [rawji's corresponding code](https://github.com/pinpox/rawji/blob/02cb559/src/rawji/fuji_usb.py#L363-L385) credits fudge. This is shared implementation lineage, not independent hardware corroboration. [Published: FilmKit, rawji] |
| `0x2019` | Device Busy | Reported from a body left unresponsive by a conversion that never completed; a power cycle clears it. [Published: grawji] |
| `0x201C` | Invalid DeviceProp Value | The property exists, but the camera refuses this value in its current state. Usually state-dependent; see [Why a write is refused](04-custom-slots.md#why-a-write-is-refused). |
| `0x201E` | Session Already Open | FilmKit's X-T3 and X100V connection logs enter its `0x201E` recovery branch: it attempts `CloseSession`, reopens and reclaims the USB connection, resets its transaction counter, then retries `OpenSession`. [Published: FilmKit, issues #5 and #8; session and transport implementations] In Filmcase's browser/WebUSB transport, a timed-out X-S10 read remains queued, and USB device close/open/interface claim is followed by `0x201E`. Filmcase reports that a Device Reset, the still-image class control request (`bRequest = 0x66` in the class definition), clears that state. Its server/PyUSB path can cancel the read through libusb and retry in place. [Published: Filmcase] See [ADR 016](https://github.com/gosku/Filmcase/blob/b8edef94e3c3fa80d96331d472388aabc84ec6ca/docs/ADRs/016-client-side-camera-transport.md#L78-L92). |
| `0xA001` | vendor-specific | A GFX100RF's answer to a bank-name write during a probe of the name's length; the source advises a shorter string. [Published: GFX100RF, fuji-ptp-notes] |

For a `0x200A` received through iOS, the rejecting endpoint can be unresolved: the published GFX100RF tether-mode comparison does not establish whether the host or camera produced it. See [platform notes](09-platform-notes.md#unadvertised-properties-macos-forwards-them-ios-might-not).

A matching, device-originated response establishes that the device answered that exchange; a value refusal alone isn't a lost connection. [Owner report: GFX100S fw 1.32] An error delivered by a host API with unresolved origin doesn't establish camera responsiveness. Neither establishes a usable session: `0x2003` SessionNotOpen, `0x2004` InvalidTransactionID, and `0x201E` SessionAlreadyOpen require session reconciliation. Keep transport responsiveness, session validity, and property support separate; see [client implementation](11-client-implementation.md).

## `GetDeviceInfo`

| Field | Fujifilm value |
|--|--|
| Vendor extension ID | `0x00000006` [Measured: X-T50 fw 1.32] [Owner report: X-T20 fw 2.01, USB diagnostics] |
| Vendor extension description | `fujifilm.co.jp: 1.0; ` (trailing space), on X-T50 fw 1.32 and X-T20 fw 2.01 alike [Measured: X-T50 fw 1.32] [Owner report: X-T20 fw 2.01, USB diagnostics] |
| `deviceVersion` | The firmware version shown in the camera's own menu. It moved from 1.32 to 2.13 on one GFX100S across a firmware update. [Owner report: GFX100S] |
| `serialNumber` | The body's serial number. Treat it as personal data. |

### The advertised lists are not complete

Never treat "not advertised" as "not present," and never read the property count as a signal. The advertised property list is wrong in both directions:

| Body | Advertised | What actually answers |
|--|--|--|
| X-T50 fw 1.31, 1.32 | 61 properties, including the whole bank block `0xD18C`–`0xD1A5` | The bank block reads on fw 1.32; `0x500F` isn't advertised and answers `0x200A`. [Measured: X-T50 fw 1.32] FilmKit's fw 1.31 vendor scan reports values for 56 of 59 advertised vendor properties; this does not establish successful reads of every advertised property. [Published: FilmKit issue #12 log] |
| X100VI fw 1.00 | 61 properties and the X-T50's 20 operations, in the same order | Not probed in the dump. [Published: libgphoto2 camera dump, paraphrased] |
| X-H2 | 61 properties | Bank reads and writes to the mapped settings `0xD190`–`0xD1A2` are reported, and a separate test wrote `0xD18E` (7 → 8); `0xD18F`, `0xD1A3`, and `0xD1A4` were read but not write-tested. All 23 codes in the [live-property map](02-properties.md#live-shooting-properties) are reported read, but the source's live-write coverage statements conflict; see the X-H2 note after this table. [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| X-M5 fw 1.30 | 61 properties | Banks 1–4 select. [Published: FilmKit issue #18] |
| X-S20 | 59 properties: the block without `0xD198` | Bank reads and writes work; `0xD198` is unsupported on the tested bank path (a write of `1` returns `0x200A`). [Published: fujicli] [Published: grawji issue #114] |
| X-S10 | 59 properties: the bank block without `0xD198` and every code in the 23-code live mirror except `0xD189` (Smooth Skin). `0x5005` and `0x5015` are present; `0xD1B2` is absent but isn't part of that mirror. `0xD16E` reads `6`. | C1–C4 reads and bank write/readback experiments are reported; the published results do not establish write testing of every bank. `0xD183` answers `0x200A` and `0xD185` `0x2002` before an upload. [Published: Filmcase, firmware unstated; see its [issue #5 dataset](https://github.com/gosku/Filmcase/issues/5)] |
| GFX100RF | 61 properties in **USB RAW CONV.** mode; 286 in **USB TETHER SHOOTING**; 5 in **USB CARD READER** | In tether mode, `0xD18C` and `0xD18D` are advertised and `0xD18E`–`0xD1A5` are not, yet they answer from a macOS host. [Published: fuji-ptp-notes] |
| X-T30 fw 2.01, X-T30 II fw 2.04 | zero properties; **USB RAW CONV.** established by `0xD16E = 6` in the X-T30 capture and reported for X-T30 II | The X-T30 converts; its separate FilmKit log reports slot-1 failure. The X-T30 II's banks read and write, with `GetDevicePropDesc` answering `0x200A`. [Captured: FilmKit #13 Profile_Read] [Published: FilmKit issue #13 log] [Community: fujifilm-ptp-recipes PR #2] |
| X-T3 fw 5.11 | 168 properties, with the `0xD162`–`0xD1FF` hole, and 27 operations | Direct bank editing unavailable in the documented **USB RAW CONV.** runs: selects 1–7 fail. Only 5 of 154 vendor properties read. [Published: FilmKit issue #5] |
| X-T20 fw 2.01 | 168 properties, with nothing between `0xD162` and `0xD1FF` | Direct bank access unsupported in the diagnostic session: all 26 `0xD18C`–`0xD1A5` reads and descriptors return `0x200A`; USB mode was not recorded. `0xD183` is unadvertised yet answers a valid descriptor. [Owner report] |
| GFX100S fw 2.13 | 168 properties, with the same `0xD162`–`0xD1FF` hole | `0xD18C`, `0xD18D`, all 23 bank properties, and `0xD1A5` answer values despite not being advertised. [Owner report] |
| X100V fw 3.01 | 4 properties, in a session where the host had just unmounted the camera; the selected USB menu mode was not recorded. [Published: FilmKit issue #8] | The dataset shape is consistent with storage mode. [Inferred] Another X100V read all its banks. [Published: FilmKit issue #1] |

In the X-T50's [FilmKit #12 log](https://github.com/eggricesoy/filmkit/issues/12), `0xD17B`, `0xD183`, and `0xD185` are absent from the successful vendor-read results; standard properties `0x5005` and `0x5015` are outside that scan. FilmKit's [reader](https://github.com/eggricesoy/filmkit/blob/9e3bbcf/src/ptp/session.ts#L278-L290) suppresses non-OK responses, empty data, and exceptions, so these omissions do not identify a refusal code or its cause. [Published: FilmKit] The local fw 1.32 observation that `0xD183` refuses a value read before a RAF upload remains separate. [Measured: X-T50; see the descriptor table later in this chapter]

For the X-H2, the source's [bank-property notes](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/properties.md#L39-L46) exclude `0xD18E`, `0xD18F`, `0xD1A3`, and `0xD1A4` from its recipe writer's write testing; a separate test wrote `0xD18E` (7 → 8). Its [live verification report](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/current-shooting-state.md#L114-L119) says all 23 live codes were written, read back changed, and restored, while its [status page](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/protocol-status.md#L116-L121) says live Lens Modulation Optimizer was never written. That inconsistency is unresolved here; neither statement establishes complete, independently verified live-write coverage. [Published: fujifilm-ptp-recipes]

The X-T20, X-T3, and GFX100S advertise the same 168 properties, and only the GFX100S answered the reported bank-block probes with values. Three bodies (X-T50, X-H2, and GFX100RF) advertise 61 in **USB RAW CONV.** mode; the X-M5 log and the X100VI dump also list 61, but neither establishes its mode, and the X100VI's attribution is inferred. Of the other bodies, two (X-S10 and X-S20) advertise 59, the X-T30 and X-T30 II report empty lists (the X-T30 capture reads `0xD16E = 6`), and the GFX100S, a GFX body like the GFX100RF, advertises 168 in the same mode, so the count follows neither the sensor line nor the processor.

Probe the read or write operation you need in the relevant USB mode and camera state. For a value read, send `GetDevicePropValue` and check both the response code and returned data before accepting a value. A failed descriptor or read doesn't establish whether a write is supported. Before any write probe, preserve the affected settings and plan restoration, then verify the result. For bank settings, follow the [bank-writing procedure](04-custom-slots.md#writing-a-bank), including read-back verification.

### Recognizing the wrong USB mode

The same GFX100S, one cable reconnection apart, gave two very different `GetDeviceInfo` datasets. [Owner report: GFX100S, 2026-09-15]

| | Storage mode | USB RAW CONV./BACKUP RESTORE |
|--|--|--|
| Dataset length | 261 bytes | 601 bytes |
| Operations | 25, including the standard upload pair `0x100C`/`0x100D` | 27, with `0x100E 0x100F 0x1017 0x1018 0x101C` instead |
| Properties | 4: `0x5001 0xD303 0xD406 0xD407` | 168 |
| Bank properties that answer | none | 26 of 28 probed |

A GFX100RF shows the same pattern across three modes: 5 properties in **USB CARD READER**, 61 in **USB RAW CONV.**, and 286 in **USB TETHER SHOOTING**. Tether mode carries the live shooting properties and, unadvertised, `0xD18E`–`0xD1A5`. [Published: GFX100RF, fuji-ptp-notes] An X100V advertised 4 properties after its host had unmounted it, but its selected USB menu mode was not recorded. [Published: FilmKit issue #8] Its dataset shape is consistent with the GFX100S storage-mode observation; this comparison does not confirm the X100V's mode. [Inferred]

To check the mode directly, read `0xD16E`, the USB mode: `5` tether shooting, `6` **USB RAW CONV./BACKUP RESTORE**, `8` webcam. libfuji's [mode-detection implementation](https://github.com/petabyt/libfuji/blob/a3bd237/lib/fuji_usb.c#L116-L133) treats a refused read as card-reader (storage) mode, with a comment allowing movie-shooting mode; it treats any other returned value as MTP. These fallbacks are implementation heuristics, not conclusive mode identification. [Published: libfuji] The X-T50 advertises `0xD16E` and reads `6` in this mode [Published: FilmKit issue #12 log, fw 1.31]. Without a usable mode read, the `GetDeviceInfo` shape is a clue. A `0xD15D`, which libfuji and libgphoto2 name SetUSBMode, exists; a GFX100S answered `0x200A` to its descriptor, and whether it switches modes is an [open question](open-questions.md#transport). [Published: libfuji] [Published: libgphoto2]

A very short, non-empty property list containing nothing in the vendor control range `0xD000`–`0xD2FF` is a storage-mode clue in these observations. An empty list isn't such a clue: an X-T30 advertised zero properties and still converted (`0xD16E = 6` in the Profile_Read capture) [Captured: FilmKit #13, fw 2.01], and an X-T30 II advertised none and still read and wrote its banks [Community: fujifilm-ptp-recipes PR #2]. The absence of any single property isn't a clue, because bodies answer properties they don't advertise. Tethered-shooting mode is a different case: it keeps a `0xD001…` control block and isn't characterized here.

## Settings backup and restore

The second half of the mode's name: in **USB RAW CONV./BACKUP RESTORE** mode, the camera exposes a backup of its settings as an object. [Published: libfuji] This record hasn't tested it; a round trip is reported to work on an X-T5 and an X-S20 [Published: fujicli] and on an X-E5, X100F, and X-T3 [Published: grawji].

- Backup: `GetObjectInfo(0)`, then `GetObject(0)`. libfuji's [download function](https://github.com/petabyt/libfuji/blob/a3bd237/lib/fuji_usb.c#L173-L244) requires **USB RAW CONV.** mode; its restore function has no equivalent mode guard. [Published: libfuji] The result is a small file (libfuji rejects anything over 100,000 bytes as a restore input; an X-T3's is about 33 KB and an X100F's about 5.6 KB [Published: grawji]). It starts with the ASCII `FUJIFILM` and carries the model name at offset `0x14` and the body's serial number in cleartext at `0x34`, so a backup is personal data and is never published. [Published: grawji]
- Restore: standard `SendObjectInfo` (`0x100C`) with parameters `[0, 0]` and an ObjectInfo whose format is `0x5000` and whose size is the backup's, padded with zeros to a fixed length (1088 bytes in libfuji, 1076 in fujicli and grawji), then `SendObject` (`0x100D`) with the backup bytes. [Published: libfuji] [Published: fujicli] [Published: grawji] The claim that Fujifilm's X Acquire sends 1076 bytes comes specifically from [grawji's comment](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/camera_backup.py#L63-L64); fujicli's matching implementation does not independently establish that provenance.
- Banks inside the backup: grawji reports backup-based editing on the X100F and X-T3, whose custom-setting banks occupy fixed-stride records with value codes that differ from the property block's. Its route selection checks advertisement, and its probe exits when `0xD18C` is unadvertised; that does not establish a direct X100F selector refusal. The X-T3 has separate failed-selector evidence; see [custom banks](04-custom-slots.md#how-many-banks). grawji expects the X-Pro2, X-T2, X-T20, X-E3, and X-T30 by layout, untested, and reaches the X-E5's FS-dial recipes through the backup too. [Published: grawji] The layouts are that project's and aren't reproduced here.

Integrity checks are body-specific. grawji's [X-T3 layout](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/backup_recipe.py#L227-L257) reports `0x200F` for a stale checksum and defines an additive 16-bit calculation over a specified payload, with exclusions and a bias. Its [X-E5 implementation](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/fs_recipe.py#L23-L26) separately reports hardware-verified checksum deltas. Its [X100F-verified layout](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/backup_recipe.py#L204-L224) declares no whole-file checksum. These source reports don't establish one universal checksum rule or the absence of every possible integrity check on an X100F. [Published: grawji]

grawji's [transfer documentation](https://github.com/p5k369/grawji/blob/7cd98fe/src/grawji/camera/camera_backup.py#L309-L316) reports `0x200F` when `GetObject` and `SendObject` share one session, without naming the body in that statement. Its backup, restore, and read-back phases therefore use separate sessions. This is reported implementation evidence, not a session-rule test on every body listed here. [Published: grawji]

## `GetDevicePropDesc` is usually refused

Descriptors would give each property's type, writability, and accepted values. Most bodies don't provide them for the bank properties, so you have to establish value sets by sweeping the camera's menu. For how to run a sweep, see [Methods](08-methods.md).

| Body | Bank properties | `0xD183` (conversion trigger) |
|--|--|--|
| X-T50 fw 1.32 | `0x2002` for every one [Measured] | `0x2002` for both value and descriptor before a RAF upload [Measured: 2026-09-14, 2026-10-03] |
| GFX100S fw 2.13 | `0x200A` for every one, while values read fine [Owner report] | Descriptor: UINT16, read/write, default `65535`, enumeration `[0, 1]` [Owner report] |
| X-T20 fw 2.01 | Descriptors refused with `0x200A` [Owner report] | Same descriptor as the GFX100S [Owner report] |
| X-H2 fw 5.20 | `0x2002` for every property, standard ones included, after an empty data phase [Published: fujifilm-ptp-recipes] | |
| GFX100RF | `0x2002` in **USB RAW CONV.** mode, while values read fine [Published: fuji-ptp-notes] | |

The refusal code itself differs by body, and neither code means the property is absent.

## Timing

| Observation | Value | Evidence |
|--|--|--|
| Bank property read | ~2–4 ms each | [Measured: X-T50] |
| Warm `GetDeviceInfo` | 5 ms (GFX100S), 9–19 ms (X-T20) | [Owner report] |
| First `GetDeviceInfo` after a cold session | 1.56 s, about 100× the warm figure | [Owner report: X-T20] |
| Accepted bank-setting write | 97–160 ms on an X-T50 and 67–135 ms on a GFX100S through ImageCaptureCore, median 118 ms on both; 55–246 ms in X RAW Studio's save. About one write in 20 takes 170–240 ms longer: 288–318 ms on the X-T50, 344–356 ms on the GFX100S. No property is consistently slow, and reads never are. See [write timing](../evidence/write-timing.md). | [Measured: X-T50 fw 1.32] [Owner report: GFX100S fw 2.13] [Captured: X-T50 fw 1.31, FilmKit #12 capture] |
| Refused bank-setting write | Three refusals near 46 ms; the Kelvin (`0xD19C`) refusal was 5.283 ms | [Captured: X-T50 fw 1.31, FilmKit #12 capture] |
| Bank name write (`0xD18D`) | The same as a bank-setting write: 76–114 ms for 41 of 47 X-T50 name writes, the two empty-name writes among them, and 103 ms for two GFX100S writes. The others were slow: 266–275 ms on the X-T50, 325 and 329 ms on the GFX100S, and 232 ms in X RAW Studio's save. | [Measured: X-T50 fw 1.32] [Owner report: GFX100S fw 2.13] [Captured: X-T50 fw 1.31, FilmKit #12 capture] |
| Select bank, then write the name | 4.676 ms between command starts: 4.291 ms for the selector transaction, then 0.385 ms from its response to the name command. No substantial settling pause in this save. | [Captured: X-T50 fw 1.31, FilmKit #12 capture] |
| Delay between property writes | none needed on an X-H2: 0 ms between property writes worked in fujifilm-ptp-recipes' application testing, and a seven-bank bench ran clean with a 50 ms pause after each select | [Published: X-H2 fw 5.20, fujifilm-ptp-recipes] |
| Live property write (X RAW Studio, after a bank save) | 4–18 ms, against 55–246 ms for accepted bank-setting writes | [Captured: X-T50 fw 1.31, FilmKit #12 capture] |
| RAF upload, 208,071,296 bytes (198.43 MiB) | 5.392 s, about 36.80 MiB/s (38.59 MB/s) | [Owner report: GFX100S] |
| X RAW Studio's own command timeout | 15 s by default in the analyzed Windows implementation, which uses WPD. The source infers that WPD opens the MTP session automatically. | [Published: fujifilm-ptp-recipes, static analysis; [timeout mapping](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xraw-studio-call-chain.md#L153-L160) and [session inference](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/reverse-engineering/xraw-studio-call-chain.md#L188-L201)] |

Two practical consequences:

- Don't tune a timeout against the warm case; the first exchange after connecting can be 100× slower.
- Scale timeouts for object transfers with their size. A 50–200 MB RAF upload or a 20 MB JPEG download takes seconds, and a flat timeout reports a working transfer as an unresponsive camera.
