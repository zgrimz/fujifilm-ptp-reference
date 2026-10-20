# 10. Reading recipe settings from a JPEG

JPEG metadata can supply a candidate recipe or help check a conversion result. Missing tags, inactive values, custom white balance, and camera-controlled settings can prevent recovery of the original intent, so keep raw metadata alongside its interpretation. A JPEG isn't a complete bank backup.

[`tools/jpeg_recipe.py`](../tools/jpeg_recipe.py) is a read-only, standard-library Python example. It extracts metadata offline, without an image library, a camera session, or any app.

## Run or import the example

```sh
python3 tools/jpeg_recipe.py JPEG_FILE
python3 tools/jpeg_recipe.py JPEG_FILE --wb-shift-scale times20
python3 -m unittest discover -s tests -p test_jpeg_recipe.py -v
```

The first command leaves WB shift scaling unresolved. Choose `direct` or `times20` only when you have an external reason to select that interpretation; `heuristic` is an explicit convenience policy. JSON goes to stdout. Exit 0 means the tool produced a result, including results with missing metadata or partial parsing; inspect the result and individual field statuses. Exit 2 indicates an input I/O failure, invalid JPEG envelope, or malformed EXIF structure. The tool opens the input read-only and doesn't save image data.

```python
# With tools/ on sys.path, or from another script in tools/:
from jpeg_recipe import parse_jpeg

result = parse_jpeg(jpeg_bytes)  # bytes, not a path
film = result["recipe"]["film_simulation"]
if film["status"] == "decoded":
    semantic_film = film["value"]
```

`parse_jpeg(data: bytes, *, wb_shift_scale="unknown") -> dict` returns a JSON-compatible dictionary. The result reports malformed image bytes; wrong Python argument types or an unknown scale option raise `TypeError` or `ValueError`. `ptpcap --metadata` uses this API on complete EXIF APP1 segments recovered from a JPEG prefix. It separately records whether the containing GetObject transfer was complete.

## From a JPEG to a candidate recipe

Start with a camera JPEG whose MakerNote is intact; sharing services and image editors might remove it. Inspect each extracted field's status, resolve ambiguities such as WB shift scale explicitly, and leave missing or unknown fields unspecified. In particular, missing WB shifts don't become zero, and missing D-Range Priority doesn't become Off.

An app can save or present the candidate recipe offline. For a [bank push](04-custom-slots.md) or [RAW conversion](05-raw-conversion.md), check the target body's supported settings and translate the semantic values through its bank or profile encodings. The extractor performs no writes. Metadata might describe an applied result rather than the user's original choice, so matching it doesn't guarantee an identical photograph.

The same extractor can also check a converted JPEG's output metadata; conversion is optional for recipe extraction.

## Evidence and source revision

The workflow draws on the JPEG metadata parsing in the author's iOS client. This project implements and checks parsing and mapping behavior independently.

The tag definitions and value meanings are Published-level evidence from Phil Harvey's ExifTool 13.55, commit [`de11d240cf7e521e939a0575a128ffe01b63be05`](https://github.com/exiftool/exiftool/tree/de11d240cf7e521e939a0575a128ffe01b63be05):

- [`FujiFilm.pm`](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm): Fuji tags and interpretation rules. Inspected file SHA-256 `01ac90924ee80c8111c87e0b8bc9d14b857c342224da3ad7b269e20177894a8e`.
- [`Exif.pm`](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/Exif.pm): ColorSpace and InteropIndex. Inspected file SHA-256 `8cd9bdb5211fbfd8e281c4879ccd587c896407f903dad57edae53684542b6989`.

Those tables themselves credit contributors and earlier research. Citing ExifTool identifies the inspected mapping source, not a new independent measurement of every body or an inspection of every original contribution. This example uses only functional tag/value facts and newly written implementation; it doesn't vendor ExifTool's implementation.

Synthetic fixtures exercise parser mechanics. Separate *capture-derived* fixtures preserve selected values from the public [FilmKit #12 X-T50 fw 1.31](https://github.com/eggricesoy/filmkit/issues/12) and [#13 X-T30 fw 2.01](https://github.com/eggricesoy/filmkit/issues/13) editor walks. Their directories and offsets have been rebuilt after removing unrelated fields. These aren't original camera JPEGs, and complete metadata doesn't establish complete image pixels. For how these fixtures were made, see [fixture provenance](../fixtures/jpeg/README.md) and the [capture reproduction procedure](../captures/reproduction.md).

## Result contract

The top-level `schema` is `fujifilm-jpeg-recipe/1`. `mapping_source` pins the lookup tables. `input` describes metadata boundaries and byte order, and always has `pixels_validated: false`. No complete-image claim follows from `status: "ok"`.

| Member | Meaning |
|--|--|
| `status` | `ok`, `partial`, `no_exif`, `no_fujifilm_makernote`, `invalid_jpeg`, or `malformed_exif`. Describes parsing, not camera compatibility or full recovery of settings. |
| `recipe` | Semantic candidate recipe fields. These contain no PTP property or conversion-profile numbers. |
| `observations` | Applied DR percentages, LMO, ColorSpace/InteropIndex, crop, and shutter metadata. These are separate from a portable recipe. |
| `camera` | Make and Model from IFD0, with the same status convention. The tool doesn't infer firmware from these strings. |
| `raw_tags` | Group, tag ID, declared TIFF type/count, storage, and relative offsets; values only for the supported metadata allowlist. |
| `issues` | Structural parsing limitations. Field-level ambiguities remain on the affected field. |

Every semantic field includes `status` and `tags`, for example `FujiFilm:0x1040`. A `decoded` field has `value` and `basis`; the basis can be a published lookup/formula, explicit signed-byte override, or caller-selected WB policy. Other statuses are `missing`, `malformed`, `ambiguous`, `unrecognized`, `unresolved`, and `inactive`. An unrecognized supported enum preserves `raw_value`; structural raw values remain in `raw_tags`. The result distinguishes a candidate film or recorded inactive value from a decoded active setting. `decoded` means that the parser applied the documented interpretation, not that the output reproduces a photograph or that a target body supports it.

The export allowlist excludes serial numbers, owners, timestamps, GPS, thumbnails, and arbitrary unknown payloads. The result records unrecognized tag IDs with type/count and `not_exported`, without values; it retains unknown values of supported numeric recipe tags. Make/Model and InteropIndex are the only exported text fields. This is a metadata filter, not a general anonymizer for hostile files that put personal text into a model field. The tool adds no source filename to the result. Don't redistribute an original APP1 segment on the assumption that it's sanitized.

## Byte parsing

1. Require JPEG SOI and walk complete, length-delimited segments until SOS or EOI. Inspect APP1 segments beginning `Exif\0\0`; skip XMP and other metadata. Don't search through entropy-coded pixels or missing bytes. Reject multiple EXIF APP1 segments as ambiguous.
2. Read the TIFF header's `II` or `MM` byte order, magic 42, and IFD0 offset. Directory entries are 12 bytes; type size × count determines whether the four-byte value cell is inline or an offset. Offset values are relative to the start of this TIFF block, bounded to this APP1 segment.
3. Follow the single ExifIFD pointer `0x8769`. MakerNote `0x927C` is an UNDEFINED byte region; its declared extent is another boundary. Follow InteropIFD `0xA005` only for the color-space observation. Reject duplicate or cyclic directory pointers. Don't traverse thumbnails, GPS, or arbitrary directory chains.
4. Check that the MakerNote begins with the eight bytes `FUJIFILM`, then read the little-endian IFD offset that follows. Its directory and offsets are little-endian and relative to the MakerNote, independently of the outer TIFF order. Neither the entry count nor an offset can escape the declared region. The parser doesn't follow a MakerNote next-IFD chain.
5. Preserve the declared raw integer and separately interpret signed fields. WC/MG have ExifTool's explicit `int8s` override: the first byte `0xEE` means −18 even when the TIFF entry declares an unsigned or larger integer. Signed SLONG tones and WB pairs remain signed. Duplicate tags, unsupported semantic types or counts, and out-of-range offsets don't become decoded fields.

The parser limits a directory to 4096 entries and exported values to small bounded metadata. It doesn't validate JPEG image dimensions, image scans, checksums, ICC profiles, or RAF/HEIF/TIFF files. A complete APP1 followed by an incomplete JPEG can yield `partial` with useful fields. A newly constructed metadata-only envelope can yield `ok`; the caller must retain its derivation context.

## Semantic fields

Types in the following table are the published Fuji tag formats. The result records a raw TIFF type separately; notably, WC/MG use a signed-byte interpretation override. Fields not present on an older body remain missing.

Numeric scalar fields accept one BYTE, SBYTE, SHORT, SSHORT, LONG, SLONG, or one-byte UNDEFINED value; the parser doesn't enforce each tag's published storage type. The WB pair specifically requires SLONG[2]. Lookup values and the selected WB policy are checked separately. A decoded numeric field therefore doesn't establish conformance to the published storage format or a body's menu limits.

| Field | Fuji tag(s), published type | Interpretation and boundary |
|--|--|--|
| Film simulation | `0x1401` SHORT, `0x1003` SHORT | Check Saturation first for monochrome/ACROS/sepia; otherwise interpret FilmMode. Missing/unknown Saturation leaves a color FilmMode as a candidate because a monochrome override is unresolved. Some legacy names remain distinct; F2/Fujichrome (`0x0200`) and F4/Velvia (`0x0400`) both normalize to `velvia`, with their distinct codes retained in `raw_tags`. |
| Color | `0x1003` SHORT | Published −4…+4 lookup. Inactive for the recognized monochrome family. The parser doesn't assign legacy `0x0200` “Low” a guessed modern dial value. |
| Sharpness | `0x1001` SHORT | Published −4…+4 lookup, for example, `0x0082` → −1 and `0x0084` → +1. Special “Film Simulation”/n/a codes don't become zero. |
| High ISO NR | `0x100E` SHORT | Published −4…+4 lookup. The parser doesn't silently substitute the older `0x100B` NoiseReduction tag. |
| Highlight/Shadow | `0x1041` / `0x1040` SLONG | `−raw / 16`, preserving fractions: −24 → +1.5; +8 → −0.5. Decoding a number doesn't establish a body's writable menu range. |
| Clarity | `0x100F` SLONG | Published multiples of 1000 from −5000…5000 → −5…+5. A value such as 1500 is unresolved as an unknown enum, not truncated to +1. |
| Grain | `0x1047` SLONG, `0x104C` SHORT | Roughness 0/32/64 → Off/Weak/Strong; size 16/32 → Small/Large. Off makes size inactive but preserves its record. Missing size with nonzero strength stays missing; nonzero strength with size Off is unresolved. |
| Color Chrome / FX Blue | `0x1048` / `0x104E` SLONG | 0/32/64 → Off/Weak/Strong, independently. |
| Monochromatic Color WC/MG | `0x1049` / `0x104B`, signed-byte override | Positive WC is warm, negative cool; positive MG is green, negative magenta. Values can be recorded while inactive. Don't infer toning availability or menu endpoints. |
| White balance | `0x1002` SHORT, `0x1005` SHORT | Named WB mode and separately recorded Kelvin. Custom1…5 identifies a stored measurement slot, not the measurement itself. Kelvin is applicable only to Kelvin mode. |
| WB shift | `0x100A` SLONG[2] | Raw Red/Blue pair, with the explicit scaling policy described in [White balance scaling](#white-balance-scaling). Missing never means `[0,0]`. |
| Dynamic range | `0x1402`, `0x1403`, `0x140B`, SHORT | User mode, manual development percentage, and Auto's selected percentage remain distinct. See [Dynamic range and priority](#dynamic-range-and-priority). |
| D-Range Priority | `0x1443`–`0x1445`, SHORT | Mode 0 Auto / 1 Fixed; Auto strength 1 Weak / 2 Strong / 3 Plus; Fixed strength 1 Weak / 2 Strong. Missing mode is unknown, not Off; whether a body omits the mode while the priority is off is an [open question](open-questions.md#jpeg-metadata). Missing Fixed strength is unresolved. |

The pinned [FilmMode definition](https://github.com/exiftool/exiftool/blob/de11d240cf7e521e939a0575a128ffe01b63be05/lib/Image/ExifTool/FujiFilm.pm#L724-L745) also questions whether the tag works on the original X100. The extractor applies the lookup without a model-specific check, so a decoded FilmMode on that body still needs independent validation.

`observations.lens_modulation_optimizer` uses `0x1045` LONG, 0 Off / 1 On. `observations.color_space` combines standard ExifIFD ColorSpace `0xA001` and InteropIFD InteropIndex `0x0001`: 1/R98 identify sRGB; Uncalibrated (`65535`) with R03 identifies Adobe RGB. A conflict is ambiguous. The parser reports ColorSpace 2 as the non-standard Adobe RGB convention and doesn't default a missing/unknown color space. Crop `0x104D` and shutter type `0x1050` are informational, without a promise that recipe pushes can change them.

### EXIF is a separate encoding namespace

For ACROS, EXIF Saturation `0x0501` is Red and `0x0502` is Yellow. The bank/profile simulation numbers in [Value encodings](03-encodings.md) are Red `0x0E` and Yellow `0x0D`. The parser emits `acros_red` or `acros_yellow`; a separate target encoder selects PTP bytes. Tones, WB shifts, grain's two JPEG tags versus its composite bank value, and all other fields need the same separation. For that separate representation, see [conversion profiles](06-conversion-profile.md).

The peer's [EXIF chapter at the inspected commit](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/exif-makernote.md) warns that Color/Sharpness might include simulation offsets, while its lookup tables also map directly to dial values. This example applies the pinned ExifTool lookup and exposes that basis. The selected public editor-walk values agree with direct mappings for Provia/Astia and Classic Chrome in those conversions; that doesn't prove every legacy body or simulation. The example applies no unverified per-simulation correction. Treat broader exact-dial recovery as an open validation question.

When checking independently, use explicit tag groups: `exiftool -FujiFilm:Sharpness`, not the bare `-Sharpness`. The public captures also carry a standard EXIF Sharpness tag; on the capture-derived fixtures, ExifTool 13.55's unqualified output selected its coarse “Soft” value instead of the Fuji −4/−2 values. A name collision isn't evidence that the Fuji recipe mapping failed.

### White balance scaling

ExifTool says newer cameras should divide WhiteBalanceFineTune by 20; it doesn't provide a universal model/firmware discriminator. Existing evidence includes:

- The [public X-T50 fw 1.31 editor walk](../captures/x-rawstudio-editor-walk-xt50-xt30.md#the-x-t50-walk-issue-12) changes the profile to R+3/B−2 and the JPEG records `[60,-40]`, establishing ×20 for that observation. [Captured]
- The X-T30 fw 2.01 walk's [recorded profile deltas](../fixtures/captures/expected.json) set cells 13/14 to −4/+4 at transaction 366, with no later WB-shift change. Its [GetObject 546 metadata](../fixtures/jpeg/capture-derived-manifest.json) records `[-80,80]` from the same source capture, another ×20 observation. The metadata APP1 is complete but the containing image transfer is incomplete. These are existing captured facts, reproduced as described in the [capture procedure](../captures/reproduction.md), not new hardware measurements. [Captured]
- The X-H2 isolation findings already cited in [metadata methods](08-methods.md#reading-a-develop-with-exiftool) report the same scale. Their [inspected EXIF chapter](https://github.com/ILFforever/fujifilm-ptp-recipes/blob/daba2d97d6b37bd1d5dbc68ca974f6b22f433071/docs/exif-makernote.md) and [source qualifications](../SOURCES.md#ilfforeverfujifilm-ptp-recipes) remain Published evidence; the source reports differing firmware versions across its pages. [Published: fujifilm-ptp-recipes]

These observations don't establish a universal model-selection rule. The tool keeps its caller-supplied scaling explicit:

| Option | Behavior |
|--|--|
| `unknown` (default) | Preserve raw pair and return `unresolved`. |
| `direct` | Interpret the pair as integer shifts; require both within −9…+9. |
| `times20` | Require both divisible by 20 and resulting integers within −9…+9. |
| `heuristic` | Choose ×20 for the pair if either magnitude exceeds 9, otherwise direct; still require valid integral results. Mark `basis: explicit_heuristic`. |

The heuristic never truncates `[9,180]` to `[0,9]` or rounds an unexplained 21 to 1. It can't establish camera compatibility and doesn't resolve which scale a zero pair used. Raw values survive every policy. A caller-supplied `times20` scale applies the same divisibility and range checks; invalid values stay unresolved without falling back to direct units. `[0,0]` decodes under `direct`, `times20`, or `heuristic`, but remains `unresolved` under the default `unknown` policy. A zero pair doesn't prove which scale the camera used. WB scaling applies only to the WB pair: it doesn't divide the separately decoded WC/MG toning values by 20.

### Dynamic range and priority

`DynamicRangeSetting=0` means Auto; `AutoDynamicRange` (`0x140B`) records the percentage chosen for the image. The parser doesn't substitute a simultaneously present `DevelopmentDynamicRange` as the user's requested DR. Setting 1 is Manual; to recover a recognized 100/200/400 recipe percentage, use `0x1403`. A manual 800 remains unresolved for the ordinary recipe set while the result retains the observed percentage; ExifTool also documents HDR percentages, and an HDR workflow needs its own context.

Older setting codes `0x0100` and `0x0201` label 100% and 400%. ExifTool's `0x0200` is the legacy Wide1 230% label, so the parser doesn't map it unconditionally to the modern DR200. `0x8000` (“Film Simulation”) also leaves numeric intent unresolved. If D-Range Priority is present, the parser marks DR and tone fields as priority-controlled rather than independent intent. It doesn't rewrite Auto's selected Weak/Strong/Plus strength as the user's Fixed choice. See [RAW conversion verification](05-raw-conversion.md) and [metadata methods](08-methods.md#reading-a-develop-with-exiftool).

## Validation and remaining work

The regression suite covers both outer TIFF byte orders, independent little-endian MakerNotes, inline/indirect values, signed-byte and signed-long values, half-step tones, ACROS Red/Yellow, both grain tags, manual/Auto/priority, unknown/missing fields, duplicate tags/APP1, invalid pointer cycles, region bounds, every truncation boundary of a synthetic envelope, and deterministic malformed bytes. It also checks the CLI and fixture hashes. If ExifTool 13.55 is installed, the suite runs it against the independently recorded expected values; it reports another installed version as skipped rather than silently changing the oracle.

The four capture-derived fixtures were generated only after ExifTool reported identical selected Fuji/EXIF values on each original complete APP1 and its sanitized reconstruction. They retain source capture hashes, GetObject transaction IDs, the source's firmware report, transfer incompleteness, and the exact selected-tag oracle results. Original capture decoding remains separately reproducible; these fixtures don't exercise original offsets or image transfers.

Additional body/firmware fixtures are needed before making broader claims about WB scaling, Color/Sharpness dial recovery, unusual legacy film modes, or how inactive fields are recorded. An importer can offer defaults as recorded application policy, but should never change a `missing`, `unresolved`, or `inactive` field into a claimed camera observation. A target encoder must independently check support, interlocks, and write/readback results as described in [client implementation](11-client-implementation.md).
