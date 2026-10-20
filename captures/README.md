# Captures

USB captures of Fujifilm's own software provide direct evidence of the exchanges they contain. Missing transfers, uncertain UI context, and inferred field meanings still limit their interpretation. They show the camera maker's client talking to the camera: the exact order of operations, timing, and which refusals Fujifilm's own tool gets and ignores.

For available inputs, hashes, commands, recovery limits, and reproducibility status, see [Reproducing the capture analysis](reproduction.md). This record doesn't redistribute raw captures or photos.

## Decoded transcripts

| Transcript | What it shows |
|--|--|
| [Bank-path evidence — X-T3 and X-T30](x-rawstudio-bank-availability-xt3-xt30.md) | Independently decoded X-T3 auxiliary-write refusals and conversion operations; captured USB-mode values; distinction between inline-log slot failures and capture evidence |
| [X RAW Studio saving a bank — X-T50](x-rawstudio-bank-save-xt50.md) | The bank write sequence, name first; the refusals X RAW Studio ignores; the 23 live writes that follow, `0xD1A5` first |
| [X RAW Studio's editor, one setting at a time — X-T50 and X-T30](x-rawstudio-editor-walk-xt50-xt30.md) | One-variable evidence for most profile cells from two public captures: cells 4, 21, and 22 settled, with the preview's MakerNote following; the X-T30's 24-cell profile and X RAW Studio's default fill of a short body's write |
| [X RAW Studio converting a RAF — X-T50](x-rawstudio-conversion-xt50.md) | The full conversion flow, `0xD212` completion polling, and how bank properties map onto profile cells |
| [X RAW Studio converting with Monochromatic Color — X-T50](x-rawstudio-toning-xt50.md) | The two toning cells, 23 warm–cool and 26 magenta–green. Toning followed explicit profile values in these X-T50 tests despite the active bank's toning; these captures don't establish how an upload seeds those cells. |

## Public captures

| Capture | Where | Contents |
|--|--|--|
| X RAW Studio on an X-T50, fw 1.31 | [FilmKit issue #12](https://github.com/eggricesoy/filmkit/issues/12) | Three USBPcap attachments named `.pcapng.gz`: Preset Save, Profile Read, RAW Conversion. The Preset Save and Profile Read files are pcapng; RAW Conversion's framing wasn't checked. The `.txt` attachments are the author's settings screens, not wire logs. The issue body also holds a full FilmKit log of the body: `GetDeviceInfo`, every bank, `0xD16E`, `0xD184`, `0xD186`/`0xD187`. Decoded here: the bank save, editor walk, and [Profile Read's header and tail changes](reproduction.md#additional-x-t50-profile-read-capture), including an accepted write with cell 29 = `1`. |
| X RAW Studio on an X-T30, fw 2.01 | [FilmKit issue #13](https://github.com/eggricesoy/filmkit/issues/13) | Four captures (Profile_Read, Preset_Save_PT1, Preset_Save_PT2, RAW Conversion) and three `.txt` settings screens. Decoded here: Profile_Read and both Preset_Save parts, in the editor-walk transcript. |
| X RAW Studio and FilmKit on an X-T3, fw 5.11 | [FilmKit issue #5](https://github.com/eggricesoy/filmkit/issues/5) | Three captures. Independently decoded here: connection commands (incoming payloads absent) and the X RAW Studio preset-change session, which confirms `0xD38C`, `0xD207`, `0xD001`, and `0xD040` writes returning `0x200A`. See the [bank-path transcript](x-rawstudio-bank-availability-xt3-xt30.md). |
| FilmKit on an X100V | [FilmKit issues #1](https://github.com/eggricesoy/filmkit/issues/1) and [#8](https://github.com/eggricesoy/filmkit/issues/8) | Four capture zips in #1 (settings read, profile read, preset save, RAW conversion), from a body whose banks were read and written; a 4-property `GetDeviceInfo` in #8 whose storage-mode interpretation is inferred, since the camera's selected USB mode was not recorded. The preset-save capture is decoded in [capture reproduction](reproduction.md#x100v-preset-save-capture): selects 1–7 and 15 name reads succeed. The other attachments aren't decoded here. |
| Nine raw `0xD185` profiles | [petabyt/libfuji](https://github.com/petabyt/libfuji) `fp/d185/` | X-H1, X-Pro3, and a 23-cell body whose files are named `xt5_*` but whose IOPCode `FF129504` matches X RAW Studio's X100F saved profile; that body attribution remains inferred and the files' origin unconfirmed; camera reads and X RAW Studio writes. See [the conversion profile](../docs/06-conversion-profile.md#lengths-seen). |
| X RAW Studio's saved profiles (FP1/FP2/FP3 XML) | [petabyt/libfuji](https://github.com/petabyt/libfuji) `fp/fp1`–`fp3` | Fujifilm's own field names, and IOPCodes for an X-H1, X100F, X-T3, and X-T5. Not PTP captures. |
| Device-info dumps | [libgphoto2](https://github.com/gphoto/libgphoto2) `camlibs/ptp2/cameras/fuji-*.txt` | `GetDeviceInfo` and descriptor sweeps for about forty Fujifilm bodies, two of which touch this record: an X100VI whose **USB RAW CONV.** mode attribution is inferred (not established by the dump or originating report) and a GFX100 II in tether mode. Not PTP captures; paraphrased here only, and the X100VI dump contains a serial number. |

GitHub attachment links redirect to a signed URL that expires within minutes. Fetch them with `curl -L` and then `gunzip`. This record links the public captures rather than re-hosting them: they contain their authors' serial numbers and, in the conversion captures, their photos.

## Unpublished captures

This record publishes only the decoded transcripts of the raw captures made for it, not the captures themselves. Any capture can include `GetDeviceInfo`, which ends with the body's serial number, and a conversion capture also contains the photo.

| Capture | Status |
|--|--|
| X RAW Studio converting a RAF on an X-T50, fw 1.32 (2026-09-07) | Held by the maintainers. It contains the photo, so only the [decoded transcript](x-rawstudio-conversion-xt50.md) is published. |
| X RAW Studio converting with Monochromatic Color on an X-T50, fw 1.32, three captures (2026-10-17) | Held by the maintainers. They contain the photo, so only the [decoded transcript](x-rawstudio-toning-xt50.md) is published. |
| X RAW Studio converting one RAF four ways on an X-T50, fw 1.32 (2026-06-24) | Held by the maintainers. They contain the photo; their cell values agree with the transcripts listed earlier (cell 21 = `1` for a frame shot with LMO On; cell 29 = `0` in every write) and nothing else from them is published yet. |
| The cell-6 probe previews, four develops of one RAF by the maintainers' client (2026-09-07) | The JPEGs behind the DR Auto finding, held by the maintainers; their MakerNotes are summarized in [RAW conversion](../docs/05-raw-conversion.md#dynamic-range). |
| GFX100S `0xD185` profile, 621 bytes (2026-09-17) | Header and first 64 bytes recorded in the owner's report. Publishing it requires the owner's agreement. |

## Decoding a capture

To decode a capture, use [`tools/ptpcap.py`](../tools/README.md), which doesn't need Wireshark. For how to make a capture and the pitfalls of large uploads, see [Capturing Fujifilm's own software](../docs/08-methods.md#capturing-fujifilms-own-software).
