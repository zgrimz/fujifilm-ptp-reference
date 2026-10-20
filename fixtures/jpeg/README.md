# JPEG fixture provenance

Every `.jpg` here is a *metadata-only JPEG envelope*, without an image scan or photo. These inputs exercise metadata parsers, and image viewers might reject them. They don't validate pixels or complete image transfers.

The `.jpg` fixtures, their JSON manifests, and expected results, and this document are covered by [CC BY 4.0](../../LICENSE) to the extent the project contributors hold the relevant rights. The Python fixture generators are covered by [MIT](../../tools/LICENSE). When sharing covered material, preserve the source attributions in the manifests. These grants do not claim ownership of the observed numeric facts or grant rights to the source captures or photographs, which are not distributed here. See the [project license scope](../../README.md#license) and [ExifTool license and use](../../SOURCES.md#exiftool-license-and-use).

## Synthetic fixtures

`synthetic-*.jpg` are deterministic, invented inputs produced by `generate_synthetic.py`. `synthetic-manifest.json` lists hashes and test purposes. The model string explicitly says `SYNTHETIC FIXTURE`. Values were selected from the published ExifTool tables; there was no camera session. The `PRIVATE-SERIAL` and `PRIVATE-OWNER` strings in one fixture are invented leak-detection sentinels, not personal data.

`exiftool-13.55-expected.json` records the selected printed values produced independently by ExifTool 13.55, commit `de11d240cf7e521e939a0575a128ffe01b63be05`. The reference parser didn't generate those expected values. Its semantic tests additionally assert the corresponding interpretations, including ACROS precedence and intentionally unresolved fields. ExifTool prints raw WB shifts; the tool's optional scale policy is tested separately.

```sh
python3 fixtures/jpeg/generate_synthetic.py
python3 -m unittest discover -s tests -p test_jpeg_recipe.py -v
```

## Extractor test vectors

[`../conformance/jpeg-extractor.json`](../conformance/jpeg-extractor.json) holds further synthetic tag sets for the extractor. Its tag lists are converted into metadata-only envelopes in memory; they don't regenerate the checked-in JPEGs, manifests, or pinned ExifTool oracle. See the [test vector guide](../conformance/README.md).

`test_jpeg_recipe.py` passes each case's explicit `input.extractor.wb_shift_scale` to the real extractor, checks its values, statuses, and privacy filtering, and serializes and reloads the result. Tests run with both outer TIFF byte orders while the Fujifilm MakerNote remains little-endian.

The cases reject fractional and out-of-range WB results without falling back to direct units, retain zero pairs without treating them as scale evidence, and keep WB scaling independent of monochrome toning. Others cover incomplete or custom WB, DRP-controlled observations, missing priority, inactive grain size, and privacy-filtered unrecognized numeric values. All are software expectations, not new camera measurements.

The malformed JPEG tests independently locate and verify their mutation targets and retain valid controls. They distinguish an IFD outside APP1 from a bad TIFF header, a cyclic ExifIFD value from a bad pointer type/count, a ColorSpace array from damaged InteropIndex metadata, and a value outside the declared MakerNote from whole-file truncation. Failures must occur for the intended reason.

## Capture-derived fixtures

`capture-derived-*.jpg` contain observed numeric tag values reserialized into new directories. Values come from complete EXIF APP1 regions within incomplete GetObject transfers in the public FilmKit captures linked in `capture-derived-manifest.json`. The source reports the firmware versions. The JPEG/TIFF layout and offsets are synthesized, so these fixtures don't test the original camera layout.

| Body reported by source | Capture | GetObject transaction IDs | Evidence retained |
|--|--|--|--|
| X-T50 fw 1.31 | FilmKit #12 `X-T50_Preset_Save.pcapng` | 1133, 1753 | Initial/final editor metadata; LMO Off/On, Adobe RGB/sRGB, Provia/Classic Chrome, manual DR100. |
| X-T30 fw 2.01 | FilmKit #13 `X-T30_Preset_Save_PT1.pcapng` | 215, 546 | Initial/final editor metadata; LMO On/Off, sRGB/Adobe RGB, Astia/Classic Chrome, manual DR100/DR400. |

`derive_public_capture.py` reads those source captures without changing them, uses `ptpcap` recovery and its complete-APP1 extraction, and rebuilds an allowlist of numeric Fuji recipe tags plus Make/Model, ColorSpace, and InteropIndex. It excludes image pixels, thumbnails, serials, GPS, dates, owners, and unrelated MakerNote fields. Before writing any fixture it requires ExifTool 13.55 to give identical selected values on the original APP1 and the new envelope. Tags are group-qualified to distinguish FujiFilm:Sharpness from standard EXIF:Sharpness.

```sh
python3 fixtures/jpeg/derive_public_capture.py DOWNLOAD_DIR/X-T50_Preset_Save.pcapng DOWNLOAD_DIR/X-T30_Preset_Save_PT1.pcapng
```

The manifest records hashes of both source captures and output fixtures, transaction IDs, transfer/APP1 completeness, the source URLs, and ExifTool's selected-tag results. Original captures contain other people's photos and serials. This record links them rather than including them. No private photograph was used. For instructions on obtaining the exact public inputs, see [Reproducing the public capture analysis](../../captures/reproduction.md).

The four capture-derived cases cover color simulations and manual DR on two bodies. ACROS, signed toning, fractional tones, and Auto/priority branches have synthetic coverage only. These reconstructions reuse the original capture observations; neither they nor the synthetic cases add independent hardware measurements or establish general camera support.
