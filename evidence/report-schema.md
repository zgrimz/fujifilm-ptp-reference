# Public evidence report, version 1

The [JSON Schema](report.schema.json) and [synthetic example](example.synthetic.json) define an implementation-neutral public export for USB observations. It carries what the maintainers' client records (immutable original snapshots, per-operation readback, connection identifiers, and trace coverage) into an implementation-neutral format; it doesn't describe that client's own report format.

For the published packages, see the [evidence index](README.md). Historical logs without per-operation timestamps or an established timezone cannot supply this schema's required timestamp fields faithfully. The [October 15 X-T50 package](xt50-20261015-224819/README.md) uses a documented companion ledger preserving source order and unknown times; it is not a version-1 report. Do not invent timestamps or connection identities to make an old log validate.

The reference also accepts owner reports supported by menu photographs. Version 1 of this schema has no menu-photo observation kind; record that evidence in a separate note with its source, displayed values, model and firmware provenance, and observation date where known. Distinguish the observation date from the date supplied. Don't invent USB connections, operations, or raw bytes to fit menu-only evidence into this format, or treat a menu value as a verified USB encoding.

```bash
python3 -m pip install -r requirements-test.txt
python3 tools/validate_evidence.py evidence/example.synthetic.json
```

Validation checks shape and consistency, including unavailable reads accidentally marked matched. It can't establish whether a hardware observation happened or whether an interpretation is correct.

## What an export records

| Field | Meaning |
|---|---|
| `schemaVersion` | Exactly 1. When meaning or required structure changes, change the version; missing legacy data stays unknown. |
| `evidenceId`, `evidenceKind` | An arbitrary report identifier and provenance: measured, captured, published, owner_report, or synthetic. No serial-derived identifier is needed. |
| `source` | Optional original URL, revision, capture SHA-256, and tool version. Record these for reproduced/published evidence; follow relays to the origin where possible. |
| `camera` | Observed model, firmware, and USB mode, each nullable when unknown. Capability entries and model guesses can't supply observed firmware. |
| `conditions` | **AUTO UPDATE CUSTOM SETTING** on/off/unknown, and relevant bank, ISO, image format, and lens presence. Unknown setup state limits the conclusion. |
| `connections` | Unique arbitrary IDs and ISO timestamps. A second connection within the same second still has another ID. |
| `observations` | Unique operation IDs linked to a connection and observation time. Preserve command outcome separately from state verification. |
| `before`, `expected`, `readback` | Maps of scoped keys to raw little-endian hexadecimal bytes. Null/missing means unavailable, not zero or Off. Keep the original before-state immutable. |
| `nameVerification` | Optional comparison result without publishing the user's bank name. |
| `metadataVerification`, `pixelsVerification`, `outputSaved`, `cleanupOutcome` | Independent results for metadata, pixels, saving, and cleanup; successful saving alone establishes no match. |
| `restartConfirmed` | Optional user confirmation of a power cycle; a changed connection ID alone doesn't establish it. |
| `trace` | Scope, retained/dropped counts, and truncation. An absent operation might fall outside that coverage. |

Keys explicitly distinguish `bank:0xD192`, `live:0xD1A5`, and `profile:8`. Bank numeric keys are limited to the 23 settings; names, serials, DeviceInfo blobs, photos, filesystem paths, and arbitrary debug strings have no fields in this public format. Numeric raw values are limited to four bytes per entry. Unknown numeric enum values can be preserved without inventing their meaning. Byte order and signed interpretation belong to the cited encoding, not to JSON's display.

A local recovery record might need more information than this public evidence export, including an original name and a locally held physical-device binding. Don't use this sanitized report as a lossless backup. Identity hashes can still identify a device across records; this schema omits them.

## Result rules

- `accepted` requires a matching OK response; `refused` requires a matching non-OK response. `outcome_unknown` means an attempted send lacks a known completion. `not_attempted` means the send wasn't reached.
- `matched` requires at least one expected field, all expected values known, and complete matching readback. Missing/failed readback can't pass. An empty expected set is `not_tested`.
- `mismatched` requires an observed unequal value. Missing fields may coexist with that difference; preserve them in the maps rather than pretending they were checked.
- A refused no-op might have matched final state. Keep both facts. No result here establishes causation from readback alone.
- Persistence should compare the accepted intended fields on a fresh connection; refusal isn't silently converted into persistence success. If no fields qualified, the settings persistence check wasn't tested.

The validator rejects unknown keys, duplicate JSON keys, inconsistent result claims, duplicate IDs, references to missing connections, and dropped trace entries without truncation disclosure. Before sharing, review the export: structured fields reduce accidental disclosure but can't prove that a user-entered model string contains no personal data.

## Reusing the format

Keep original evidence immutable; when knowledge changes, append a separately identified correction or interpretation. Separate a raw observation from the body-wide capability conclusion it supports. A schema-valid synthetic report is useful for integration testing but never expands the hardware matrix. The report is intentionally small; link additional evidence, such as a sanitized capture transcript, with its source and method rather than embedding it as an unrestricted debug dump.
