# Synthetic test vectors

These cases give inputs and expected outcomes for the reference's own tools. They're synthetic software tests, not camera observations or a certification of compatibility. They use no photos, serial numbers, or camera connection.

## Files

| File | What it tests |
|--|--|
| [`cases.json`](cases.json) | Command-outcome and field-verification examples for adapting to a client's own tests. |
| [`binary.json`](binary.json) | `bankprobe.py`'s response-container checks, USB stream framing (split and coalesced reads), and PTP string decoding. |
| [`workflows.json`](workflows.json) | `bankprobe.py`'s write blocking after a lost reply to a bank name or setting write. |
| [`jpeg-extractor.json`](jpeg-extractor.json) | `jpeg_recipe.py`'s decoding of synthetic MakerNote tag sets, and the JSON round trip of its result. |

The three versioned files have `schema_version: 1`, a `provenance` object with `kind: "synthetic"` and `hardware_evidence: false`, and a `cases` array. Each case has a stable `id`, `kind`, `input`, `expected`, and `coverage.reference`, which names the checks that execute it. A `policy` records the parsing or write rule a case exercises. Numeric values and codes in JSON are decimal unless a field explicitly contains hexadecimal text.

## Binary cases

`input.hex` contains one complete message or string; stream cases instead use `input.chunks_hex`. A successful response and a well-formed refusal are both structurally valid; acceptance of the operation is a separate result. Complete-buffer checks aren't USB read-boundary rules: `bankprobe.py` consumes a byte stream, so bytes after one container are kept for the next read. Malformed cases can name a `control` case and a byte `mutation`; the fixture checks rebuild that mutation and confirm its target.

## Workflow cases

`input.initial` declares the starting state and `input.events` the ordered events; `input.writes` and the injected `input.fault` drive the probe's offline test transport. Under the stop-after-unknown policy, a write whose reply is lost blocks the later writes, automatic cleanup, and the next bank until the outcome is reconciled.

## JPEG cases

Tag inputs are synthesized with the existing [JPEG generator](../jpeg/generate_synthetic.py), and the case's extractor options are passed explicitly to the real parser. Expected paths address fields in its JSON result; absent paths and excluded text check that missing settings or private payloads aren't manufactured or exported. The extractor's WB shift scale defaults to `unknown`; a case that passes `times20` tests decoding under that scale. See [extractor test vectors](../jpeg/README.md#extractor-test-vectors).

## What runs here

| Coverage label | Check |
|--|--|
| `fixture_integrity` | Unique IDs and JSON keys, required fields, coverage labels, encodings, and control/mutation relationships, in [`test_conformance.py`](../../tests/test_conformance.py). |
| `jpeg_extractor` | Real `parse_jpeg` results compared with the expectations, in [`test_jpeg_recipe.py`](../../tests/test_jpeg_recipe.py). |
| `extractor_json_round_trip` | The extractor's result survives JSON serialization. |
| `bankprobe_transaction` | Real probe transaction code with offline fake endpoints, in [`test_bankprobe.py`](../../tests/test_bankprobe.py). |
| `bankprobe_stream` | Real probe stream framing with fragmented and coalesced input. |
| `ptp_string` | Real probe PTP string parsing. |
| `bankprobe_write_policy` | Real probe write and cleanup blocking after a lost reply. |

Every case in the three versioned files is executed by at least one tool check besides `fixture_integrity`. `cases.json` gets fixture-integrity checks only. Run the [offline checks](../../tools/README.md#evidence-validation-and-the-offline-checks); passing them establishes the tools' software behavior, not camera compatibility. Record model and firmware results separately in the [evidence format](../../evidence/report-schema.md).

## Provenance and reuse

The cases were written from client failure patterns, the reference's framing and metadata descriptions, and published metadata mappings. Hardware-derived mappings keep their existing sources and evidence scope; synthetic boundary values aren't camera measurements. Fixture data and this document use [CC BY 4.0](../../LICENSE); the Python tests use [MIT](../../tools/LICENSE), under the repository's license scope.
