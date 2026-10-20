# Fujifilm PTP reference

This reference is a single starting point for implementing Fujifilm recipe writes and in-camera RAW development, with a traceable record of what's been tested and what's still uncertain. It also covers reading recipe settings from JPEGs shot on Fujifilm cameras.

What's known about Fujifilm's USB/PTP interface comes mostly from reverse engineering and is spread across other projects' apps, libraries, and notes. Each project uses its own code, names, and indexing, and mixes the protocol facts with its own implementation choices. This reference separates the facts from those choices, reconciles the conflicting conventions, and states each fact independently of any app or implementation. Every detailed claim carries a tag that says where it came from: a measurement, a capture of Fujifilm's own software, a camera owner's report, or another project's published finding. For what each project contributed, see [Credits](#credits) and [`SOURCES.md`](SOURCES.md).

The reference also adds original work:

- Hardware experiments on an X-T50: write tests, sweeps, and RAW conversions
- USB captures of Fujifilm's X RAW Studio, and new analysis of public captures
- [Corrections](docs/errata.md) where published sources disagree with the hardware or with each other
- Python tools that extract JPEG metadata, decode USB captures, and run bank experiments

[Camera bodies](docs/07-cameras.md) records what's been tested on each X-series and GFX body; [open questions](docs/open-questions.md) lists what's still uncertain and the experiment that would settle each one.

> This project isn't affiliated with FUJIFILM Corporation. FUJIFILM, X RAW Studio, and camera model names are trademarks of FUJIFILM Corporation, used here only to identify the hardware described.

## Choose a workflow

| Starting point | Workflow | Start here |
|--|--|--|
| A recipe to save on a camera | Select and back up the target bank, encode the requested settings, write in dependency order, and read the settings back to verify them. | [Custom-setting banks](docs/04-custom-slots.md) |
| A RAF to develop | Upload a RAF the connected body shot, under the name `FUP_FILE.dat`. Change the requested settings in its conversion profile, trigger conversion, then download the image produced by that conversion and inspect its metadata. | [In-camera RAW conversion](docs/05-raw-conversion.md) |
| A Fujifilm JPEG | Extract recipe settings and raw metadata without connecting a camera. Before encoding settings for a target body, review unknown or missing fields. | [JPEG recipe extraction](docs/10-jpeg-recipes.md) and `python3 tools/jpeg_recipe.py JPEG_FILE` |

The bank selector (`0xD18C`) can retain a previous host's selection; select the target before each bank operation. The [client guide](docs/11-client-implementation.md) covers combining these workflows in an app, including operation locks, partial failures, and recovery.

## Scope

Camera procedures primarily use **USB RAW CONV./BACKUP RESTORE** mode. Some bodies also expose banks in tether mode; see [transport and session](docs/01-transport.md). The reference covers device discovery, bank and live properties, conversion profiles, JPEG MakerNotes, and the USB stacks used to investigate them.

Wi-Fi and Bluetooth, remote shutter control, a tethered-shooting API, general mass-storage and MTP file transfer, and camera firmware internals are outside this reference's scope. The reference includes tether-mode observations where they clarify bank or live-property behavior.

Before you connect a camera, read the [warranty note and how to protect saved settings](#before-you-connect-a-camera). Verify every write by reading it back; an OK response alone doesn't establish that a setting changed.

## Documents

|     | Document                                                         | What it covers                                                                                                                                                                  |
| --- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | [Transport and session](docs/01-transport.md)                    | USB mode, PTP framing, response codes, `GetDeviceInfo`, descriptors, timing                                                                                                     |
| 2   | [Property reference](docs/02-properties.md)                      | Every vendor property code seen, with type, access, and meaning                                                                                                                 |
| 3   | [Value encodings](docs/03-encodings.md)                          | How each bank setting is encoded on the wire                                                                                                                                    |
| 4   | [Custom-setting banks](docs/04-custom-slots.md)                  | Reading and writing C1–C*n*: sequence, ordering, refusals, gating, restore                                                                                                      |
| 5   | [In-camera RAW conversion](docs/05-raw-conversion.md)            | The conversion flow, completion, verification, dynamic range, and white balance                                                                                                 |
| 6   | [The `0xD185` conversion profile](docs/06-conversion-profile.md) | Binary layout, field table, host-write form, parsing safely                                                                                                                     |
| 7   | [Camera bodies](docs/07-cameras.md)                              | What is known per body; bank counts, firmware additions, and menu controls from Fujifilm's manuals; film simulation dials                                                       |
| 8   | [Methods](docs/08-methods.md)                                    | How to establish a fact about a camera, and the traps that produce false ones                                                                                                   |
| 9   | [Platform notes](docs/09-platform-notes.md)                      | ImageCaptureCore on iOS, iPadOS, and macOS; WebUSB and other host stacks                                                                                                        |
| 10  | [Reading recipe settings from a JPEG](docs/10-jpeg-recipes.md)   | Reading a recipe back from a JPEG's MakerNote: bounded parsing, decoding, unknown and missing values                                                                            |
| 11  | [Implementing a recipe client](docs/11-client-implementation.md) | Recommendations for a client: operation ownership, snapshots, partial failures, session lifecycle                                                                               |
| —   | [Corrections to published sources](docs/errata.md)               | Where FilmKit, rawji, and others disagree with the hardware                                                                                                                     |
| —   | [Open questions](docs/open-questions.md)                         | What isn't known yet, and what would settle it                                                                                                                                  |
| —   | [Captures](captures/README.md)                                   | Known USB captures, decoded transcripts of X RAW Studio, and how to reproduce the analysis of the public ones                                                                   |
| —   | [Evidence index](evidence/README.md)                             | Original-record availability, source conflicts, closure criteria, and sanitized evidence packages                                                                               |
| —   | [Public evidence report](evidence/report-schema.md)              | A portable, sanitized format for observations, with explicit verification states                                                                                                |
| —   | [Tools](tools/README.md)                                         | `ptpcap.py` and `verify_capture.py` for USB captures; `bankprobe.py`, a USB probe that runs the record's sweeps and write tests on a body; `jpeg_recipe.py`; the offline checks |

## Evidence

The protocol record combines camera observations, controlled probes, captures of Fujifilm's X RAW Studio, and attributed findings from other projects. Fujifilm's own manuals, firmware notes, and support pages supply menu facts: which controls and values a body's menu offers, and the ISO floors it states. They describe the menu, not what a body answers or accepts over USB, and the record carries them only where they have a USB anchor: a fact explains an observation the record holds, or bounds a bank property on a body with protocol observations; see [facts from Fujifilm's manuals](docs/07-cameras.md#facts-from-fujifilms-manuals). JPEG interpretation also draws on published metadata mappings. Evidence tags identify those sources and distinguish inference; they don't certify an interpretation or compatibility with an untested body.

Detailed protocol claims carry source tags; summaries link to those chapters. Tags appear in square brackets with the body, firmware, and date where they apply: `[Measured: X-T50 fw 1.32, 2026-09-17]`.

| Tag | Meaning |
|--|--|
| Measured | Observed by this project's maintainers, directly on a body or on a host connected to one, with one variable changed at a time. |
| Owner report | Observed by a camera's owner, with inspectable supporting evidence such as raw diagnostic data or photographs of the camera's menu screens. The tag names that method, and the claim covers only what the evidence shows. |
| Captured | Seen in a USB capture of Fujifilm's own software (X RAW Studio) talking to a camera. |
| Published | Taken from another project's source or documentation, or from Fujifilm's own manuals, firmware notes, or support pages, and not independently confirmed here. A manual tag (`[Published: Fujifilm manuals]`) covers what the menu offers, not USB behavior. When the original evidence has been inspected, prefer it and credit its origin. If only a relay was inspected, identify it and the reported origin explicitly. Unmarked rules remain identified as such; a relay isn't independent corroboration. |
| Community | A second-hand report that something works on a body, without inspected evidence establishing the claim. |
| Inferred | Reasoned from other evidence; not observed. |

An owner report's tag names the method after the body and firmware, for example `[Owner report: GFX100S fw 2.13, menu photographs]`. Menu photographs show what the camera displays: setting names, displayed values, and the limits of a setting's range. They don't show how the camera encodes a value over USB, whether it accepts that value in a USB write, or whether it keeps the value after you save or reconnect.

Where sources disagree, the order of trust is: a capture of Fujifilm's own software or a measurement on hardware, then an owner report, then a published source, then inference. This order applies only between sources that address the same claim. For example, a menu photograph outranks a published source on what the menu displays, but it can't settle a disagreement about a USB encoding. A single body's behavior is a fact about that body. Claims about a whole sensor line or processor generation say so explicitly and say how many bodies they're based on.

Attributions and claim scope are checked source by source against the revisions inspected in October 2026, and selected profile-cell mappings rest on the [capture analysis](captures/README.md). A citation check doesn't re-run hardware experiments or establish that every interpretation of a measurement is correct. [`SOURCES.md`](SOURCES.md) records inspected revisions and source lineage; [open questions](docs/open-questions.md) lists the unresolved hardware and provenance questions.

## Before you connect a camera

### Warranty

Connecting third-party software to a Fujifilm camera might void its warranty. Two sources report that Fujifilm takes this position. Neither cites a Fujifilm document, and this record can't confirm or rule out either one.

- Ritchie Roesch at Fuji X Weekly reports that, according to Fujifilm, using any non-licensed program, including Fujifilm's own SDK, "to connect to, or control, any compatible Fujifilm camera, will void the camera's limited product warranty." He says he confirmed this with Fujifilm. He also notes that warranty laws vary by country and region, and that Fujifilm might still honor a voided warranty. For the full article, see [Your Camera's Warranty Might Be Voided](https://fujixweekly.com/2026/06/08/your-cameras-warranty-might-be-voided/). [Published: Fuji X Weekly, 2026-06-08]
- The fujifilm-ptp-recipes README warns that using this protocol might void a camera's warranty. It states that Fujifilm has said, verbally, that third-party USB/PTP access is covered by the same warranty clause as its SDK EULA (section 5.2). It doesn't say who Fujifilm said this to. [Published: fujifilm-ptp-recipes README]

By the Fuji X Weekly wording, the risk covers any connection, including one that only reads settings. Extracting recipe settings from JPEGs doesn't involve the camera. If your camera is still under warranty, check the warranty terms and consumer laws where you live before you connect it.

### Protect saved settings

Writing to a camera changes the settings its owner has saved. No known operation in the bank-property path clears a bank. The camera menu's **ERASE** command erases one, but what an erased bank reads over USB is untested, so a property snapshot can't promise to restore that state. This gap is specific to the bank properties: it doesn't show that no other USB command can clear a bank, or that the separate whole-settings backup can't restore one. Encodings confirmed on one body aren't guaranteed on another.

To protect saved settings:

1. Before you write, read and save every original value you need to restore, including the bank name. If you can't read one, stop.
2. After each write, read the value back to verify it.
3. Tell your users what your restoration procedure actually recovers. Grain's remembered size can be reconstructed on the tested X-T50 and GFX100S with a size-setting write followed by Off; writing Off alone can leave the wrong size. For details, see [Client implementation](docs/11-client-implementation.md).

## Contributing

Observations from bodies other than the X-T50 are the most valuable thing this record can receive. For what to send and how to capture it, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Credits

This record builds on FilmKit, rawji, libfuji, and libgphoto2; takes facts from fujicli, grawji, and Filmcase; and is cross-checked against fujifilm-ptp-recipes (X-H2, X-T5, X-Pro3) and fuji-ptp-notes (GFX100RF). The record notes shared source lineage rather than counting it twice. The tkcranny/fxraw project mapped film simulations `0x11`–`0x14` from X100VI profile dumps. For what each contributed and under which license, see [`SOURCES.md`](SOURCES.md).

The record grew out of Fuji Cookbook, the maintainers' iOS client for these protocols; the X-T50 measurements come from that client and from `tools/bankprobe.py`, and the record states every fact independently of the app.

## License

Copyright 2026 Zachary Grimshaw.

- The documents and fixture data — Markdown files, JSON data files other than the executable schema `evidence/report.schema.json`, and the metadata-only `.jpg` fixtures in `fixtures/jpeg/` — are licensed under [Creative Commons Attribution 4.0 International](LICENSE) (CC BY 4.0), to the extent the project contributors hold copyright or applicable database rights in them. When sharing covered material, credit this record and the identified contributors, retain supplied copyright, license, and warranty-disclaimer notices, link to the [project](https://github.com/zgrimz/fujifilm-ptp-reference) and license, and indicate modifications. Do not impose additional legal or technological restrictions that prevent others from exercising the licensed rights. For the full conditions, see the license.
- The Python code in [`tools/`](tools/) and `tests/`, the fixture generators in `fixtures/`, the evidence-package exporters in `evidence/`, and the executable schema `evidence/report.schema.json` are licensed under the [MIT License](tools/LICENSE). Fixture data keeps the source attribution its manifests give.

The license does not create ownership of individual protocol constants, byte offsets, or value encodings. Implementing those functional facts is distinct from reproducing copyrightable text or a protected selection or arrangement of a table, whether in documentation or code. CC BY 4.0 also covers any applicable database rights the project contributors hold. Third-party material retains its identified rights and notices; these licenses grant only rights the contributors can grant. See the [licensing note](SOURCES.md#licensing-note) and the [JPEG fixture provenance](fixtures/jpeg/README.md).

If this reference helps your implementation, please consider crediting it alongside the relevant upstream sources identified throughout.

FUJIFILM, X RAW Studio, and the camera model names are trademarks of FUJIFILM Corporation and aren't covered by either license.
