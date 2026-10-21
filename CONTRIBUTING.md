# Contributing

The most valuable contribution is evidence from a body other than the X-T50. A single report from a body with no evidence yet can settle questions that no amount of reasoning can. For what's wanted most, see [open questions](docs/open-questions.md). Send observations as [issues](https://github.com/zgrimz/fujifilm-ptp-reference/issues).

## What to send

For every observation:

- Body and firmware, and how each was established, such as the camera's menu or the owner's confirmation. Mark unknown details.
- Observation date, where known; distinguish it from the date the evidence was supplied.
- What you did, step by step, including anything you changed in the camera's menu.
- What the camera's own menu showed, if you compared.

For USB observations, also send:

- USB setting (it should be **USB RAW CONV./BACKUP RESTORE**).
- Raw bytes: property codes with their values in hex, and response codes for anything refused. "It didn't work" can't be acted on; `0xD190 ← 0x0190 → 0x201C` can.

Menu-only observations can use a short evidence note with the supporting photographs or a source reference, the displayed values, and the scope of the conclusion. A photographed menu endpoint establishes a menu limit; USB encodings and accepted writes need their own evidence.

Most useful, roughly in order:

1. Decoded `GetDeviceInfo` fields, with the serial number removed: operations, properties, formats, vendor extension, model, and firmware.
2. A read of every bank, the 23 settings and the name, with the bank count found by selecting upward until refused. Record `0xD1A5` separately as a live observation; it doesn't belong in a bank-only restore.
3. A menu comparison: does what you decoded match the camera's own menu, row by row?
4. A capture of X RAW Studio doing one thing (saving one bank, or converting one RAF), as the decoded transcript [`tools/ptpcap.py`](tools/README.md) prints. See [Capturing Fujifilm's own software](docs/08-methods.md#capturing-fujifilms-own-software).
5. A write probe or full write pass on a bank you've backed up, followed by a power cycle.
6. A profile harvest: the `0xD185` profile after uploading a RAF your body shot.

[Methods](docs/08-methods.md) describes each of these and the traps to avoid. [`tools/bankprobe.py`](tools/README.md#bank-research-probe) produces 1, 2, and 5 from a computer over USB, and runs the sweeps that settle the entries in [open questions](docs/open-questions.md).

## Before connecting your camera

Connecting third-party software might void your camera's warranty; see [Warranty](README.md#warranty).

Writing changes your saved settings. No clearing operation is characterized in this bank-property path; the camera's own menu offers **ERASE**. What the separate settings-backup path can restore isn't established here. Before you write to a bank, save every one of its properties, including its name. Write only to a bank you can spare.

## Privacy

- Don't send serial numbers, or hashes of them. A serial is short enough to recover from its hash. The maintainers' iOS client's keyed identifier, marked `hmac-sha256`, is the exception: it's computed under a key that never leaves your phone, so a guessed serial can't be checked against it.
- Don't send raw captures. Any capture can include `GetDeviceInfo`, which ends with your serial number, and a capture of a RAW conversion also contains your photo. Send the decoded command stream instead: [`tools/ptpcap.py`](tools/README.md) suppresses the `GetDeviceInfo` payload and raw photo data. The operation name and payload length can still appear.

## How claims are recorded

Detailed protocol claims carry an evidence tag (see [Evidence](README.md#evidence) in the README). Where known, record the body, firmware, and date, identify how those details were established, and mark missing details as unknown. Qualify owner reports by their method, such as menu photographs or USB diagnostics, so the tag doesn't imply evidence beyond what was supplied. A contribution changes a claim's tag or adds a body to it; it doesn't replace earlier evidence without saying so. Where your body disagrees with a documented one, the record keeps both. Facts taken from Fujifilm's manuals, firmware notes, or support pages are menu statements, tagged as such, and recorded only where they have a USB anchor: a fact explains an observation the record holds, or bounds a bank property on a body with protocol observations; see [facts from Fujifilm's manuals](docs/07-cameras.md#facts-from-fujifilms-manuals).

## Structured observations

For USB observations, use the [report schema](evidence/report-schema.md) to keep the raw values; the model, firmware, and USB mode; the **AUTO UPDATE CUSTOM SETTING** state; the writes attempted; what the read-back showed; and what couldn't be restored. Label synthetic fixtures and mocked client behavior apart from camera runs. For a capture, give the public attachment's identifier and hash and the decoder invocation, as [capture reproduction](captures/reproduction.md) does, not the raw photo or the device serial.

Version 1 of the schema has no menu-photo observation kind. Record menu-only evidence in a separate note; don't invent USB connections, operations, or raw bytes to make it fit the schema.

## Reviewing a change

Before a release, review the claims that changed as well as running the [offline checks](tools/README.md#evidence-validation-and-the-offline-checks). Look for wording that turns an observed body into a generation-wide rule, a matching readback into proof of causation, a state-dependent refusal into absence, or a scoped unknown into impossibility. Recheck README summaries against the detailed chapters. A clean phrase search or structural check can't establish these distinctions.

## Contribution licensing

By submitting material for inclusion, you agree to license your original documentation and fixture data (including JSON data and metadata-only JPEG fixtures) under [CC BY 4.0](LICENSE), and your original Python code, fixture generators, tests, and contributions to `evidence/report.schema.json` under the [MIT License](tools/LICENSE). You retain your copyright; no copyright assignment is required. These terms apply only to rights you hold and can grant, not to ownership of individual protocol facts.

Identify any third-party material, its source, and its license or other basis for inclusion. Preserve its attribution, notices, and evidence provenance; do not assume that a public repository or a citation grants permission to copy protected material. The [README license section](README.md#license) records the project-wide scope.
