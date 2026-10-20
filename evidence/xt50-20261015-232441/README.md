# X-T50 October 15 confirm run: sanitized evidence

This package makes the recovered `bankprobe-20261015-232441.json` independently inspectable through a deterministic, allowlisted derivative. It records historical X-T50 firmware 1.32 observations; it is not a new hardware test. The [evidence index](../README.md) explains the files; the [October records note](../xt50-october-records.md) relates this run to the others.

The original's SHA-256 is `eebcebf1f9613e80cc6939c302ff5f2f8ec69abb91131a55efe8e00bb9208975`; it and its paired transcript stay in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, at the paths the [manifest](manifest.json) and [findings](findings.json) record. The chapters cite a selected subset of this run, not the complete run exported here.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 1,888 original array entries in order: 1,820 transaction records and 68 host reconnect-event records. |
| [`snapshots.json`](snapshots.json) | Seven before and seven after snapshots; 23 bank settings are separated from live `0xD1A5`. |
| [`findings.json`](findings.json) | Ten reviewed finding projections, including operator-reported menu observations and the partial Image Size experiment whose original summary was discarded. |
| [`manifest.json`](manifest.json) | Original and artifact hashes, coverage counts, unknown conditions, and omission rules. |
| [`export.py`](export.py) | Run-specific typed finding projection and hash-pinned source selection, using the [shared exporter](../bankprobe_package.py). |

The ledger retains 1,647 scalar payload fields and omits 97 non-allowlisted payload fields. It records 1,743 OK responses, nine refusals, and 68 transactions without a recorded completion. Those incomplete operations retain `response: null`, `outcome: "outcome_unknown"`, and whether a transport error was recorded. Unknown completion establishes neither success nor refusal. These are host-generated report rows; camera-origin responses have not been independently correlated with a bus capture.

Finding and detail indices are zero-based; `sourcePointer` values identify original JSON fields. Referenced transcript line numbers are one-based.

## What the recovered run supports

Menu changes and ISO/format conditions are associated with operator prompts and continuation. The package contains no independent photograph or telemetry of those menu states.

| Topic | Scoped observation |
|---|---|
| LMO and Color Space | Finding 0 records `0xD1A3` as `1/2` at the ON/OFF prompts and `0xD1A4` as `2/1` at the Adobe RGB/sRGB prompts. |
| White Balance | Finding 1 records AUTO WHITE PRIORITY `32800`, AUTO AMBIENCE PRIORITY `32801`, UNDERWATER `8`, SHADE `32774`, FLUORESCENT LIGHT 1 `32769`, INCANDESCENT `6`, AUTO `2`, and CUSTOM 1 `32776`. Recorded WB-shift changes accompany several prompts. These are eight tested labels, not an exhaustive enum test. |
| Bank Image Size | Finding 2 records L 16:9 / L 1:1 / M 3:2 / S 3:2 / L 3:2 as `0xD18E=8/9/4/1/7`; the corresponding `0xD1A5` samples are all `7`. |
| Image Quality | Finding 3 records FINE / NORMAL / FINE + RAW / NORMAL + RAW / RAW as `0xD18F=2/3/4/5/1`. |
| Live Image Size | Finding 4 samples C7/C6 bank sizes `9/7`, with live size `7/7`. A direct `0xD1A5=7` write receives OK and reads `7`; the operator then reports a `1:1` menu aspect ratio. The live write repeats the already-held value. AUTO UPDATE state was requested but not recorded, so this does not resolve the menu/readback disagreement or prove that the bank was unexpectedly saved. |
| Selector | Finding 5 records a reported body bank C7 while the USB selector reads `6`; after selecting C7 it reads `7` after cable reconnect and after the body-C6 prompt. The subsequent unselected Film Simulation read is `12`, matching the earlier C7 sample rather than C6's `11`. These are this run's reported conditions, not a guarantee for all body/menu transitions. |
| HEIF comparison | Finding 6 records Clarity `40` accepted/read back on C7 and `0` refused with `0x201C`/read back `0` on C6 during the HEIF prompt. Both writes receive OK during the JPEG prompt. These are no-op writes of held values: their differing responses support the observed bank-associated refusal, not a new setting change or a universal detector of format. |
| ISO and Dynamic Range | Finding 7 records the response/readback matrix after this table for the prompted ISO values. It does not establish behavior on other bodies or at every intermediate ISO. |
| Partial Image Size gate test | Finding 8's original `detail` is null and its summary says skipped. The ledger and paired transcript nevertheless preserve a Digital Tele-Converter ON/OFF comparison completed before the HDR prompt was skipped; see [Partial Digital Tele-Converter experiment](#partial-digital-tele-converter-experiment). |
| No-name control | Finding 9 records Film Simulation `12→2→2`. Ledger indices `1587/1607/1608/1619` provide initial read, write, immediate read, and post-procedure read. No name write appears between the setting write and post-procedure read. The paired transcript records OFF / wait five seconds / ON and operator continuation. This contradicts the stale header predicting loss, but does not isolate all prior session effects or unknown AUTO UPDATE state. |

| Prompted ISO | DR100 | DR200 | DR400 | Raw `65535` |
|---|---|---|---|---|
| 125 | OK, reads 100 | `0x201C`, reads 100 | `0x201C`, reads 100 | OK, reads 65535 |
| 250 | OK, reads 100 | OK, reads 200 | `0x201C`, reads 200 | OK, reads 65535 |
| 500 | OK, reads 100 | OK, reads 200 | OK, reads 400 | OK, reads 65535 |

### Partial Digital Tele-Converter experiment

The paired transcript, `transcripts/bankprobe-20261015-232441.txt` in the archive, has SHA-256 `df4f55cd6bddeb12da79ce0e82fb06a18fd06adb089287bcd8d25566d499c9d1`, also recorded in the [source inventory](../xt50-october-sources.json). Lines 625–637 associate two completed attempts with the Digital Tele-Converter ON and OFF prompts:

| Prompted condition | Write index | Written `0xD18E` | Response | Read index / value |
|---|---:|---:|---|---|
| Digital Tele-Converter ON | 1562 | 7 | `0x201C` | 1563 / 7 |
| Digital Tele-Converter OFF | 1571 | 7 | `0x2001` | 1572 / 7 |

Earlier attempts at indices 1555 and 1564 have transport errors and no recorded completion; they are retained separately from the completed retries. Both completed attempts write the already-held value, so equal readback does not convert the refusal into acceptance or prove a size change. The paired transcript records the HDR prompt being skipped at lines 639–640. Thus the run contains a finite, operator-mediated Tele-Converter response comparison, but no completed HDR trial or Sports Finder control.

`findings.json` explicitly labels these two rows as recovered ledger observations with separately reviewed transcript context. The exporter rebuilds their numeric values from the JSON ledger. Their fixed prompt associations were checked against the hash-pinned transcript; the exporter does not reread that private transcript or present the null original finding as containing the rows.

### Final numeric state

C1–C6 match their initial snapshots for all 23 exported bank settings. C7 differs in four settings:

| Property | Before, unsigned | After, unsigned |
|---|---:|---:|
| `0xD199` White Balance | 4 | 32776 |
| `0xD19A` WB shift R | 9 | 0 |
| `0xD19B` WB shift B | 65527 | 0 |
| `0xD1A3` LMO | 1 | 2 |

Every paired `0xD1A5` sample matches. These are live samples taken while selecting banks, not seven separately stored live settings. Don't describe the run as an exact full-run restore. Individual write helpers might restore a later baseline after manual menu changes; the before/after differences alone do not identify their cause. Names are omitted, and snapshots do not establish name restoration or power-cycle persistence.

## Conditions and limits

The original records model X-T50, firmware 1.32, and local start time `2026-10-15T23:24:41`. USB mode, **AUTO UPDATE CUSTOM SETTING** state, timezone, and lens state remain unknown. ISO and image format vary by prompted subtest; the manifest's run-wide ISO is therefore null. A requested AUTO UPDATE setting is not proof of its observed state. Earlier name writes elsewhere in the run also prevent interpreting the no-name control as a session with no previous name writes.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261015-232441/export.py \
  ARCHIVE_DIR/bankprobe-20261015-232441.json --check
```

To regenerate the four machine-readable artifacts, omit `--check`. To compare a fresh export separately, add `--output-dir OUTPUT_DIR`. The exporter checks the original's exact hash, rejects an original located in the checkout, and reads without modifying or copying it. The manifest records data-artifact hashes plus the run-specific and shared exporter hashes. This README is separately reviewed interpretation. The public tests do not need private originals or establish that hardware observations occurred:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the repository's documentation license; exporter code and tests are MIT-licensed.
