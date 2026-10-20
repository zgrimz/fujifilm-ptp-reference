# X-T50 October 15–16 records

This note connects the [published packages](README.md#available-x-t50-packages) to the original October 15–16 runs and states what each run does and doesn't establish. The originals are in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, directory `hardware-runs/bankprobe-x-t50-2026-10-15`. The archive's README identifies one X-T50 fw 1.32, test bank C7, and comparison bank C6. The packages export those runs; they aren't new hardware tests.

The directory holds 67 files: 48 JSON logs, 18 transcripts, and a README. No original log, transcript, bank backup, bank name, or identity payload is copied into this reference. The [source inventory](xt50-october-sources.json) records the SHA-256, Git blob hash, byte length, and archive path of the 22 original files this note uses.

## October 15 runs

| Original JSON | SHA-256 | Published package |
|---|---|---|
| `bankprobe-20261015-224819.json` | `cd14cc1d2fee70b7d19706cdc4e5a47e39008c365d475aba42bfb9e054f6b28c` | Guided run: 1,654 operation rows and 38 reconnect-event rows, ten findings, seven before/after bank snapshots, paired transcript. [Sanitized pilot package](xt50-20261015-224819/README.md). |
| `bankprobe-20261015-232441.json` | `eebcebf1f9613e80cc6939c302ff5f2f8ec69abb91131a55efe8e00bb9208975` | Confirm run: 1,820 operation rows and 68 reconnect-event rows, ten findings, seven before/after bank snapshots, paired transcript. [Sanitized confirm-run package](xt50-20261015-232441/README.md). |

The chapters cite an extraction from these files, not the full arrays; the files' identity doesn't make the probe's automated verdicts correct.

The first run's DR test refuses `0` with `0x201C`, accepts `65535` and `100`, and reads each accepted value back. With priority values `0→2→0`, DR reads `100→100→100`. This supports the recorded X-T50 observations, not a conclusion about an X-H2 placeholder. Its `name-last` finding records persistence after a settings-and-name sequence; that alone cannot establish a name-write commit requirement. The public pilot records these limits and the before/after snapshot differences instead of copying the original verdict strings.

The second run's numeric findings retain the bank/body HEIF comparison and the ISO125/250/500 DR responses. At ISO125, DR200/400 are refused; at ISO250, DR200 is accepted and DR400 refused; at ISO500 both are accepted. The ISO and menu changes are operator-mediated setup. Its final `d18e-gates` detail is null, but the ledger and paired transcript preserve a partial test before HDR was skipped: after the Digital Tele-Converter ON prompt, `D18E=7` receives `0x201C` (indices 1562/1563); after the OFF prompt, the same bytes receive `0x2001` (1571/1572). Both readbacks are already `7`. This is an operator-mediated refusal/acceptance comparison, not proof of a changed Image Size or an independently measured mode state. Earlier attempts 1555/1564 have unknown completion. It does not supply the missing Sports Finder comparison or an HDR result. Its `no-name-control` records persistence despite a stale test header predicting loss.

## Reset and name-timing reconciliation

The three October 16 runs have original JSONs and transcripts with operator observations, and sanitized [name-timing](xt50-20261016-094028/README.md), [reset-check](xt50-20261016-095611/README.md), and [power-dot](xt50-20261016-100752/README.md) packages. All indices in this note are zero-based positions in the original `transactions` array, not PTP transaction IDs. Transaction IDs repeat after sessions/reconnects.

| Run | Inspected original observations | Scope |
|---|---|---|
| `bankprobe-20261016-094028` — `name-timing` | Film Simulation alternates `12→2→12→2→12`, with accepted writes and matching reads. Name writes at indices 37, 47, 62, and 76 correspond to immediate, reported ten-second delay, new PTP session, and cable-reconnect conditions. The operator reports the dot in all four. | Name writes did not clear the dot under these conditions. During the first inspection, entering the item and backing out cleared it; the second response explicitly says the item was not entered. The other later responses report the dot before saving without explicitly recording item-entry behavior. |
| `bankprobe-20261016-095611` — `reset-check` | Bare write `12→2`: write 62, immediate read 63, post-RESET read 78 = `2`. With name: write `2→12` at 98, read 99, name write 100, post-RESET read 115 = `12`. Both procedures prohibit entering EDIT/CHECK or opening an item, and the operator reports RESET was available and performed; the responses do not independently confirm every navigation restriction. | Two changed-value RESET controls retain the USB value. A third write at 135/read 136 remains `2` at 151 after entering/leaving the item clears the dot and disables SAVE/RESET. |
| `bankprobe-20261016-100752` — `power-dot` | Initial `12` at 15; write `2` at 35/read 36; name write 37. The operator reports a dot before the instructed power cycle and none after; fresh read 48 is `2`. | This particular persistence/dot-clearance case includes a name write. |

Three other runs narrow the disagreement rather than removing it:

- `002045`, working-copy: initial Film Simulation `12` at index 9, accepted write `2` at 29/read 30, then post-RESET `12` at 45. This remains a reverting counterexample. The operator inspected the custom-settings menus before RESET; exact item-entry behavior and AUTO UPDATE state are unconfirmed. A later stage retains a changed `12→2`, while its final stage merely rewrites the already-held `2`.
- `003651`, markers: the bare changed-value write remains `2` after RESET. Its later “write then name” stage rewrites an already-held `2`; the operator reports RESET was grayed out. The tool's “kept after reset” summary cannot establish that RESET was executed, so this stage isn't a RESET control; a count that includes it overstates the controlled evidence.
- `090027`, bank-switch: a bare `12→2` survives switching C7→C6→C7 with matching Q-menu observation. The next “write+name” stage sends a name after that same value was already inspected and bank-switched, with no intervening Film Simulation write. It does not isolate a name write as the cause of dot clearance.

The [custom-bank chapter](../docs/04-custom-slots.md#persistence-and-the-red-dot), [methods](../docs/08-methods.md#persistence-check), and [open questions](../docs/open-questions.md#bank-protocol) keep the conflicting early reset result and cite the two explicit `reset-check` controls rather than an aggregate RESET count.

## Power-cycle evidence

Five cases pair an OFF / wait five seconds / ON instruction and operator continuation with a fresh read of a changed Film Simulation value. Three omit a name write and two include one. These are operator-mediated power-cycle observations, not independent power-state telemetry; a reconnect alone would be insufficient.

| Run / test | Initial → written → post-cycle | Original indices: initial / write / immediate read / post-cycle |
|---|---|---|
| October 15 `224819`, name-last | `15→2→2` | 1389 / 1409 / 1410 / 1423 |
| October 15 `232441`, no-name-control | `12→2→2` | 1587 / 1607 / 1608 / 1619 |
| October 15 `235633`, fresh-pull | `12→2→2` | 12 / 32 / 33 / 43 |
| October 15 `235805`, fresh-close | `12→2→2` | 12 / 32 / 33 / 44 |
| October 16 `100752`, power-dot | `12→2→2` | 15 / 35 / 36 / 48 |

A reported loss after a no-name write has no surviving record; the October 15 `no-name-control` run does not show that loss.

## Conditions and remaining work

- The **AUTO UPDATE CUSTOM SETTING** state remains unknown. Earlier prompts mention saving manually or using AUTO UPDATE, and the October 15 `232441` and October 16 `000308` instructions ask for DISABLE. A procedure's requested state is not an explicitly recorded observation of that state, and cannot establish the setup of later runs.
- Run/event times are local, without an offset or timezone. Operation rows have no timestamps. The three October 16 target logs contain no `0xD16E` USB-mode read. Preserve these limits rather than assigning the current computer's timezone or assuming a mode from successful access.
- Names, name bytes, DeviceInfo, and other identity payloads remain private. Any public persistence export should report name equality without exposing the name.
- Both October 15 runs and the three named October 16 runs have [public packages](README.md#available-x-t50-packages). The second October 15 final C7 snapshot differs in WB mode, both WB shifts, and LMO. The October 16 cleanup sequences verify 21 bank fields plus live `0xD1A5`, omit fresh final Kelvin/Color reads, and end with unknown CloseSession completion; exact whole-bank restoration is not established. A controlled AUTO UPDATE comparison, the early loss record, and exports of other earlier comparison runs remain separate follow-ups. No image/pixel-method or external-source conflict is closed by these bank logs.
