# X-T50 October 15 run: sanitized numeric evidence

This package makes the recovered `bankprobe-20261015-224819.json` run independently inspectable without publishing the private original. It contains a deterministic, allowlisted derivative of the existing X-T50 firmware 1.32 report. It is not a new hardware test. For how to read the files, see the [evidence index](../README.md).

The original's SHA-256 is `cd14cc1d2fee70b7d19706cdc4e5a47e39008c365d475aba42bfb9e054f6b28c`; it stays in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, outside this repository, at the path the [manifest](manifest.json) records. The chapters cite a selected subset of this run, not the complete run exported here.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 1,692 original array entries in order: 1,654 transaction records and 38 host reconnect-event records. One JSON object per line. |
| [`snapshots.json`](snapshots.json) | The seven before and seven after snapshots, with 23 numeric bank settings separated from live `0xD1A5`. |
| [`findings.json`](findings.json) | Typed numeric details from eight selected source findings. Prompt labels are fixed reviewed labels; original verdict prose and `ok` flags are omitted. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, coverage counts, conditions, omission rules, and exporter hash. |
| [`export.py`](export.py) | Run-specific exporter that refuses any original whose hash differs from the reviewed file. |

The ledger retains 1,529 scalar payload fields and omits 80 non-allowlisted payload fields. Recorded responses comprise 1,597 OK responses, 19 refusals, and 38 transactions with no recorded completion. Those last transactions keep `response: null`, `outcome: "outcome_unknown"`, and the presence of a transport error; the error text is omitted. Don't interpret an absent response as a refusal, a success, or evidence of camera liveness. Responses come from a host-generated report, not an independently correlated bus capture.

## What the recovered run supports

These are scoped observations from this run. Menu labels and format transitions are operator-prompted associations recorded by the original tool; this package contains no independent photographs of the selected menu state.

| Topic | Evidence and limit |
|---|---|
| Film simulation | Source finding 0 records the nine prompted labels and their read values: PRO Neg. Hi/Std `4/5`, Monochrome `6`, Monochrome + Ye `7`, Sepia `10`, ACROS `12`, and ACROS + Ye/R/G `13/14/15`. It is not an exhaustive enum test. |
| LMO and Color Space | Source finding 1 records `0xD1A3` changing `1→2` at the LMO prompt, no change in the compared fields at the Long Exposure NR prompt, and `0xD1A4` changing `1→2→1` at the Color Space prompts. “No change” does not prove the absence of a separate Long Exposure NR property. |
| DR Priority interaction | Ledger indices `722/723`, `756/757`, and `790/791` pair `0xD190=100` with `0xD191=0→2→0`. This is an X-T50 observation. The original finding 2's X-H2 placeholder interpretation is not exported or adopted. |
| DR candidate values | Source finding 4 and ledger indices `854–859` record `0xD190=0` refused with `0x201C` and readback 100, followed by accepted/read-back `65535` and `100`. Refusal and unchanged state are separate facts. |
| Toning | Source finding 5 records accepted/read-back raw `0`, `10`, `65526`, `180`, and `65356` on each toning property after simulation `12`; tested `5`, `9`, `65527`, and `190` were refused. Further toning attempts after simulation `10` were refused. This establishes these tested points and conditions, not all intermediate values or a rendered-pixel effect. |
| Monochrome color controls | Source finding 6 sets ACROS, then records finite writes/readbacks for Color Chrome Effect, Color Chrome FX Blue, both WB shifts, and Color. The refused `0xD19F` no-op still has equal readback; equal final state does not turn that response into acceptance. |
| HEIF/JPEG prompts | Source finding 7 records `0xD1A2=40/50` refused during the HEIF prompt and `50/40` accepted/read back during the JPEG prompt. `0xD18F` read 4 in both phases. The refused write of the already-held value 40 illustrates why outcome and state verification are independent. These results do not identify a general format detector. |
| Bank size versus live size | Source finding 8 is supported by ledger indices `1325–1331`: bank property `0xD18E` accepts 9 and reads back 9; live `0xD1A5` reads 7, including after changing bank selection. The reported target 9 belongs to the bank-size write. It is not a direct `0xD1A5=9` write trial. |
| Selector | Source finding 3 reports selector values `7/7/7/7` before, selected, after cable, and after the menu prompt. This does not prove that a different body-menu bank was actually selected. |
| Final numeric state | C1–C6 have matching before/after values for all 23 retained bank settings. C7 differs in three settings, listed after this table. Don't describe this run as an exact full-run restore. Names are omitted, and neither name restoration nor power-cycle persistence is established by the snapshots. |

The final C7 bank snapshot differs from the initial C7 snapshot as follows:

| Property | Before, unsigned | After, unsigned |
|---|---:|---:|
| `0xD190` DR | 200 | 100 |
| `0xD192` film simulation | 12 | 15 |
| `0xD1A3` LMO | 1 | 2 |

Each paired before/after `0xD1A5` sample matches. These are observations of live state while a bank is selected, not seven independently stored live-setting values. The comparison is relative to the run's initial snapshot; individual test helpers might use later baselines after prompted manual changes. A difference does not, by itself, identify which helper or manual action caused it.

Original finding 9's name-as-commit interpretation is also omitted. A settings/name/power-cycle sequence without controlled ordering and AUTO UPDATE conditions cannot isolate a commit mechanism. The underlying transaction headers remain in the ledger, with name bytes removed.

## Conditions and unresolved limits

The original records model X-T50, firmware 1.32, and local start time `2026-10-15T22:48:19`. Its USB mode, **AUTO UPDATE CUSTOM SETTING** state, timezone, lens state, and ISO are not established by this report. Format changes are associated with the original prompted subtests; they are not a continuous independent format measurement. Do not infer these conditions from later runs or manufacturer capability tables.

## Reproduce and verify

Keep the immutable original in a private archive outside the checkout. From the reference repository root, verify the existing package with:

```bash
python3 evidence/xt50-20261015-224819/export.py \
  ARCHIVE_DIR/bankprobe-20261015-224819.json --check
```

To regenerate the four machine-readable artifacts, omit `--check`. To compare a fresh export separately, add `--output-dir OUTPUT_DIR`. These paths are placeholders. The output embeds the original's archive-relative path and SHA-256 (the `source` block of `manifest.json`), never a local filesystem path. The exporter reads the original without modifying or copying it, checks the exact original hash, and rejects originals located inside the checkout. JSON output and the manifest are deterministic; the manifest records SHA-256 hashes of all three data artifacts and the exporter. This README is a separately reviewed interpretation, not an exported source verdict.

Public regression tests require no access to the original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_packages.py' -v
```

The tests exercise privacy boundaries, unknown outcomes, scoped snapshot fields, source-hash rejection, and artifact hashes. They do not establish that a hardware observation happened. The evidence text/data follow the repository's documentation license; `export.py` and its tests are MIT-licensed.
