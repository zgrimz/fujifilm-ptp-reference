# 9. Platform notes

The protocol is the same everywhere. Getting PTP commands to the camera isn't, and each USB stack has its own traps.

## iOS and iPadOS — ImageCaptureCore

The maintainers' client drives this stack end to end with an X-T50 on iPhone and iPad (iOS/iPadOS 26 and 27). [Measured: X-T50 fw 1.32] Owner reports from a GFX100S and an X-T20 came through the same framework. [Owner report: GFX100S fw 2.13] [Owner report: X-T20 fw 2.01] fuji-ptp-notes drives a GFX100RF through the same framework from iOS 26 and macOS 26, and is the source of the host comparison later in this section. [Published: GFX100RF, fuji-ptp-notes]

### Discovery

- Keep one `ICDeviceBrowser` for the life of the process. A new browser created in the same process didn't reliably re-announce an already-attached camera, and the second connect waited out its discovery timeout until the process restarted. [Measured: X-T50, iOS 26]
- `ICDeviceBrowser.devices` (iOS 13+) is a synchronous list of devices already found by that browser. Apple documents it as empty before the first `didAdd`; it does not independently enumerate an attached camera. The browse mask combines a device type with a location: `ICDeviceTypeMask.camera | ICDeviceLocationTypeMask.local` for local devices, including USB. `browsedDeviceTypeMask` is available from iOS 15.2. [Published: Apple SDK, `ICDeviceBrowser.h` and `ICDevice.h`]

### Authorization: two grants, not one

| Grant | What it allows | Where the user sees it |
|--|--|--|
| Control | Controlling the camera, including PTP commands | **Settings → Privacy & Security → Camera** [Measured: X-T50, iOS 26] |
| Contents | Accessing device contents; without it the camera is never posted to the browser | **Settings → Privacy & Security → Files and Folders** [Published: Apple Developer Forums, user report in [thread 765768](https://developer.apple.com/forums/thread/765768)] |

Request both grants. Without contents authorization, iOS enumerates the camera but never posts it to the browser: `didAdd` doesn't fire while the control grant looks correct, and the only diagnostic is a device-console line from `icprefd-xpc` ("User denied or disabled … access to contents on external device"). [Measured: X-T50, iOS 26, one device] Apple's [contents-authorization API](https://developer.apple.com/documentation/imagecapturecore/icdevicebrowser/requestcontentsauthorization%28completion%3A%29) is available from iOS 14.

### Sessions and commands

- Check the `ICCameraDeviceCanAcceptPTPCommands` capability in `capabilities`. There is no boolean property of a similar name. [Published: Apple SDK, `ICCameraDevice.h`]
- Open the session with the completion-handler form, `requestOpenSession(options:completion:)`, which delivers the `NSError` through its completion handler. [Published: Apple SDK, `ICDevice.h`]
- Right after plug-in, the device might report that it's busy enumerating (`-9954`). Retry the open. [Measured: X-T50, iOS]
- A session left open by an earlier connection can make a fresh open fail. [Measured: X-T50, iOS] Close it and reopen, and keep the client's request identity separate from ImageCaptureCore's wire transaction numbering. On direct USB, `0x201E` means Session Already Open (see [response codes](01-transport.md#response-codes)).
- Send commands with `ICCameraDevice`'s `requestSendPTPCommand`. Pass a complete PTP command container (length, type, code, transaction ID, parameters — see [framing](01-transport.md#ptp-framing)) and the data phase as `outData`. The X-T50 sessions in the next two items use this framing.
- In the reported X-T50 sessions, a response ID differed from the client-supplied ID: the first client command after opening received response ID 6, and a client that compared the two IDs failed its conversion check. [Measured: X-T50 fw 1.32, iOS, 2026-10-15 and 2026-10-17] Renumbering by a framework that shares the session with its own traffic is an explanation inferred from this mismatch; the inspected Apple API declarations do not document that mechanism. As a client recommendation, serialize requests and correlate each response through its request-specific callback/context and session identity. Arrival order alone doesn't distinguish a late completion from the current request; reject stale completions without advancing the current operation.
- One reported connection of 301 commands covered bank reads and writes, two 87 MB uploads, and four conversions. Every response was recorded as a well-formed response container, each converted JPEG's `GetObjectInfo` dataset was 114 bytes, and each `GetObject` was recorded as delivering the declared size. [Measured: X-T50 fw 1.32, iOS 27.0.1, 2026-10-18] The ObjectInfo layout matched the Windows X RAW Studio toning capture's. [Captured: X-T50 fw 1.32, 2026-10-17 toning capture] The Windows capture's JPEG downloads are truncated; see [the converted object](05-raw-conversion.md#the-converted-object). These observations concern the reported sessions. Clients still need to validate response framing and received lengths.
- Serialize commands and whole operations. Allow one command in flight, and keep select → dependent writes → verification → restore under one operation owner, so nothing else changes the bank selector between commands. The same ownership boundary covers a complete upload → profile → trigger → download → cleanup conversion, including competing probes and batch jobs. See [client implementation](11-client-implementation.md).
- As a client policy, time out every command, scaled by payload size (the maintainers' client uses a 20 s floor plus one second per MB). If a sleeping camera or stalled pipe leaves a completion undelivered, every later command otherwise waits behind it. This budget is an implementation choice, not a protocol requirement.
- Tag each command (for example, through the `contextInfo` argument of the selector-based form) and ignore completions for any command but the current one. A command that timed out can still complete later, while the next one is in flight. [Measured: X-T50, iOS]

### Unadvertised properties: macOS forwards them, iOS might not

Bodies answer properties they never advertise (see [transport](01-transport.md#the-advertised-lists-are-not-complete)), so whether the host lets such a command through matters. The evidence disagrees, and both readings are recorded:

| Host | Body, mode | Unadvertised property | Result | Evidence |
|--|--|--|--|--|
| macOS 26 | GFX100RF, **USB TETHER SHOOTING** | `0xD18E`–`0xD1A5` | forwarded; a write to `0xD192` on C7 held | [Published: fuji-ptp-notes] |
| iOS 26 | GFX100RF, **USB TETHER SHOOTING** | `0xD18E`–`0xD1A5` | `0x200A`, with `0xD18D` (advertised in that mode) writing fine from the same phone in the same session as the control | [Published: fuji-ptp-notes] |
| iOS 26 | GFX100S, **USB RAW CONV.** | `0xD18C`–`0xD1A5`: 26 unadvertised codes, including live-state `0xD1A5` | all 26 values answered; name and 20 of 22 parameters written, with `0xD191` and `0xD1A5` refused; successful settings and name persisted after power cycle | [Owner report: GFX100S fw 2.13] |
| iOS 26 | X-T20, USB mode unrecorded | `0xD183`, not advertised | a valid descriptor answered | [Owner report: X-T20 fw 2.01] |

The GFX100RF range in the table is fuji-ptp-notes' block-level conclusion. Its [concrete experiment](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/EXPERIMENTS.md#L7-L32) is `0xD192 = 11` on C7, retained after moving the bank cursor away and back; it publishes no exhaustive per-property transaction log or power-cycle check for that write. The [same-phone, same-session `0xD18D` control](https://github.com/Junsudo/fuji-ptp-notes/blob/f662d3c/EXPERIMENTS.md#L69-L75) is explicitly reported. [Published: fuji-ptp-notes]

fuji-ptp-notes concludes that iOS refuses the unadvertised property before it reaches the camera. Its first three README revisions retained uncertainty about which endpoint refused it and called for a USB capture. [Commit `748b7c9`](https://github.com/Junsudo/fuji-ptp-notes/commit/748b7c94be64192b85135707eb6d5b9be111bdb2) removed that caveat without adding supporting published evidence. The history cannot establish what unpublished evidence existed. [Published: fuji-ptp-notes, commit history]

The GFX100S owner report shows unadvertised-property access from iOS in **USB RAW CONV.** mode; the X-T20 adds a successful unadvertised descriptor in an unrecorded mode. These reports rule out an iOS refusal of every unadvertised property. The GFX100RF source already reports iOS bank-write success in RAW conversion mode and failure in tether mode, but changing modes also changes which properties that body advertises. A controlled comparison should record both advertised lists, the same target property, phone, OS build, and session conditions, checking whether the target remains unadvertised. A USB capture of the failing exchange is needed to determine whether the request reaches the camera. Until then, a `0x200A` received through iOS might originate at either endpoint. **USB RAW CONV.** remains the recommended mode for bank work based on the reported successes. See [open questions](open-questions.md#transport).

### Disconnection

- In one reported X-T20 session, `didRemove` arrived 6.1 s after close, then 2.3 s, then never; the next connect found the device already known. [Owner report: X-T20 fw 2.01]
- A power-cycled GFX100S reportedly took longer to reappear than a client's reconnect attempts allowed. When the user has been asked to switch the camera off and on, allow a long window. [Owner report: GFX100S fw 2.13]
- A response known to originate at the camera establishes that it answered that exchange; a PTP-shaped error delivered by the host alone does not establish its origin or camera liveness. Session usability is a separate question: treat `0x2003`, `0x2004`, and `0x201E` apart from value refusals (see [response codes](01-transport.md#response-codes)).

### ImageCaptureCore error codes

The inspected `ICReturn…` error enums share `ICErrorDomain`; check the error domain before classifying an arbitrary `NSError` by number. Constant names in the following table omit the common `ICReturn` prefix. [Published: Apple SDK, `ImageCaptureConstants.h`]

| Code | Constant | Meaning in practice |
|--|--|--|
| `-21343`, `-21249` | ConnectionNotAuthorizedToOpenDevice, PTPNotAuthorizedToSendCommand | Authorization |
| `-21345`, `-21344`, `-9927` | ConnectionFailedToOpen, ConnectionFailedToOpenDevice, DeviceFailedToOpenSession | Connection/device/session open failed; a wrong USB mode is one unconfirmed explanation |
| `-9943`, `-9953` | DeviceIsPasscodeLocked, DeviceNeedsCredentials | |
| `-21349`, `-21348`, `-21350` | ConnectionClosedSessionSuddenly, ConnectionEjectedSuddenly, ConnectionDriverExited | Unexpected session close, ejection, or driver exit |
| `-9958` | SessionNotOpened | Session is not open; it might never have opened successfully |
| `-9923` | CommunicationTimedOut | |
| `-9954` | DeviceIsBusyEnumerating | Still cataloging its card; retry |

## macOS — ImageCaptureCore and the camera daemon

Native macOS uses the same framework and `requestSendPTPCommand`, but the public authorization APIs differ. Apple's [`requestContentsAuthorization`](https://developer.apple.com/documentation/imagecapturecore/icdevicebrowser/requestcontentsauthorization%28completion%3A%29) and [`requestControlAuthorization`](https://developer.apple.com/documentation/imagecapturecore/icdevicebrowser/requestcontrolauthorization%28completion%3A%29) are available on iOS/iPadOS and Mac Catalyst; the SDK declarations mark them unavailable on native macOS. This API distinction doesn't establish the absence of analogous macOS privacy checks. [Published: Apple API documentation and `ICDeviceBrowser.h`] A sandboxed Mac app is reported to need the USB entitlement under **App Sandbox → Hardware** before discovery works. [Published: [Apple Developer Forums, thread 756960](https://developer.apple.com/forums/thread/756960)]

One host difference is reported for a GFX100RF: macOS accepted the unadvertised-property operation where iOS returned `0x200A` (previous section). fuji-ptp-notes used **USB TETHER SHOOTING** mode for both bank and live writes from macOS, and **USB RAW CONV.** mode for bank writes from iOS. The rejecting endpoint in the iOS tether-mode case remains unresolved. [Published: GFX100RF, fuji-ptp-notes]

On macOS, another camera application or the camera daemon can prevent a host from claiming the PTP interface. [FilmKit issue #2](https://github.com/eggricesoy/filmkit/issues/2) includes successful connections after closing Photos or QuickTime. The maintainer's explanation is tentative and distinguishes WebUSB's ability to claim the interface from native applications. [Published: FilmKit, user reports and maintainer explanation]

The [X-T30 II fw 2.04 report in fujifilm-ptp-recipes PR #2](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/11ee783b8df4133a615f359ee2a12e0775337f38/docs/tested-bodies.md#L74-L78), using macOS 26 and a Python/pyusb/libusb script, says normal termination of `ptpcamerad` did not help, force-termination did, and launchd restarted it, requiring a prompt interface claim. That is a workaround reported for that setup; it does not establish that every native host requires a daemon kill. [Community: fujifilm-ptp-recipes PR #2] `tools/bankprobe.py` also requires an available interface; its [README](../tools/README.md#bank-research-probe) recommends quitting applications that already own it.

## Other stacks

fujifilm-ptp-recipes' FujiSync (Android USB host, claiming the PTP interface class `0x06` directly), FilmKit (WebUSB from Chromium-based browsers; Safari and Firefox don't implement it), fujicli and grawji (libusb/pyusb on Linux), libgphoto2, and any direct libusb host carry the same containers as [framing](01-transport.md#ptp-framing) describes. The Linux examples do not imply exclusive platform support; fujicli also supports macOS. These stacks have not been independently hardware-tested in this reference. fujifilm-ptp-recipes' protocol page gives 16 KiB bulk chunks and a 5 s command timeout as typical values, and found 0 ms between property writes enough on an X-H2. [Published: fujifilm-ptp-recipes]

FilmKit's README and issues collect the host-side traps for WebUSB: camera-interface contention on macOS, the WinUSB driver (Zadig) on Windows, Chromium refusing a protected interface class on some bodies, and a udev rule on Linux. [Published: FilmKit]

At the [inspected revision](../SOURCES.md#inspected-revisions-and-source-paths), libgphoto2 defines no Fujifilm property at `0xD18C` or `0xD18D` and has no dedicated Fujifilm bank or RAW-conversion workflow. Its generic property access does not supply those workflows. In its pinned header those numbers are other vendors' codes: `0xD18C` and `0xD18D` are Canon EOS custom functions 13 and 14 ([`ptp.h` line 2218](https://github.com/gphoto/libgphoto2/blob/92171a382f185f617e95cb9acecf2d43688b19ab/camlibs/ptp2/ptp.h#L2218)), and `0xD18D` is also Nikon's `IndicatorDisp` ([line 2625](https://github.com/gphoto/libgphoto2/blob/92171a382f185f617e95cb9acecf2d43688b19ab/camlibs/ptp2/ptp.h#L2625)); the vendor namespace matters. The Fujifilm bank codes appear as unnamed entries in its contributed camera dumps. [Published: libgphoto2]
