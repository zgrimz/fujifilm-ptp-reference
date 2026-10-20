# X-T50 October 16 power-dot run: sanitized evidence

This package contains a deterministic, allowlisted derivative of the recovered `bankprobe-20261016-100752.json` run on X-T50 firmware 1.32, bank C7. It pairs a changed Film Simulation write and a name write with an operator-mediated power-cycle procedure and dot observations. It is a historical test, not a new hardware run. The [October records note](../xt50-october-records.md) compares it with the other persistence cases; the [evidence index](../README.md) explains the files.

The original's SHA-256 is `176a885cc91f476decedb6fe4e94ba3df5055c4caee13df8d639adf8df119532`; it and its paired transcript stay in the maintainers' private archive at revision `803067ca4b4aefaf9849e4bda0209317a9ff2582`, at the paths the [manifest](manifest.json) and [findings](findings.json) record. The transcript's procedure references are reviewed annotations; the exporter doesn't re-read it.

## Files and coverage

| File | Contents |
|---|---|
| [`transactions.jsonl`](transactions.jsonl) | All 125 original entries in order: 121 operation rows and four host reconnect-event rows. |
| [`findings.json`](findings.json) | Numeric trial, name equality comparisons, normalized dot observations with source pointers, the power instruction's evidence basis, and limited cleanup comparison. |
| [`manifest.json`](manifest.json) | Source and derivative hashes, counts, conditions, omissions, and hashes of both exporter modules. |
| [`export.py`](export.py) | Run-specific projection using the shared [package exporter](../bankprobe_package.py); rejects any original with a different hash. |

The ledger retains 103 scalar payload fields and omits ten other payload fields. It records 115 OK responses, no recorded refusals, and six operations with no response. Unknown operations retain `response: null`, `outcome: "outcome_unknown"`, and transport-error presence without error prose. A missing completion is not a refusal or acceptance, and host reconnect events alone do not establish power cycling. Responses are from a host-generated report without independently correlated bus provenance.

The original has no top-level before/after snapshot pair; no snapshot artifact is invented.

## Persistence and dot observation

| Step | Source evidence | Result |
|---|---|---|
| Initial Film Simulation | Read at index 15 | `12`, response `0x2001`. |
| Change Film Simulation | Write 35; immediate read 36 | Intended `2`, write response `0x2001`, read response `0x2001` and value `2`. |
| Write name | Index 37 | Response `0x2001`; private bytes compare equal to the name initially read at 10. Contents omitted. |
| Inspect before power instruction | Original `/findings/0/detail/before`; transcript 42–43 | Operator answers affirmatively to the dot prompt. The short answer does not independently distinguish the C7-row dot from the Film Simulation-list dot. |
| Instruct OFF / wait five seconds / ON | Paired transcript 45–46 | Tool instructions and operator continuation, without independently measured power state or elapsed time. |
| Fresh Film Simulation read | Index 48 | `2`, response `0x2001`. |
| Inspect after power instruction | Original `/findings/0/detail/after`; transcript 49–50 | Operator reports no red dot. |

The menu instructions prohibit opening Film Simulation or another item. The brief responses do not explicitly confirm that every navigation restriction was followed. Findings separate the requested behavior from recorded observations.

This supports the reported persistence and dot clearance for this write-plus-name sequence, with an operator-mediated power cycle. It is not an instrumented restart proof, a bare-write test, or a demonstration that the name write caused persistence. It neither establishes AUTO UPDATE state nor resolves the earlier reset disagreement. The accepted setting write and its matching reads are independently visible from the operator's dot observations.

## Cleanup and conditions

Cleanup writes/readbacks at indices 79–120 cover 21 of the 23 bank settings, each with `0x2001` and values matching the initial reads. Live `0xD1A5` at 121/122 also matches its initial sample. `0xD19C` Kelvin and `0xD19F` Color are neither written nor freshly read in cleanup. Name write/read 77/78 matches the initial name; final name write 123 sends those same bytes but has no later readback. CloseSession 124 has a transport error and no response. A later manual-save/Q-menu check is instructed without an explicit recorded result. Exact whole-bank restoration and later persistence are not established.

The local start time is `2026-10-16T10:07:52`, without offset/timezone. USB mode, **AUTO UPDATE CUSTOM SETTING**, ISO, lens state, and image format are unconfirmed. There are no independent menu photographs or rendered-pixel evidence in this package.

## Reproduce and verify

Keep the immutable original outside the checkout. From the reference repository root:

```bash
python3 -B evidence/xt50-20261016-100752/export.py \
  ARCHIVE_DIR/bankprobe-20261016-100752.json --check
```

To regenerate the three machine-readable artifacts, omit `--check`. To write them to a separate directory, add `--output-dir OUTPUT_DIR`. The exporter checks the exact original hash, rejects an original inside the checkout, and never modifies or copies it. The manifest hashes both data files and both exporter modules. This README is separately reviewed interpretation. Public regression tests need no original:

```bash
python3 -B -m unittest discover -s tests -p 'test_evidence_package*.py' -v
```

Evidence text/data follow the documentation license; Python exporters and tests are MIT-licensed. Reproduction/privacy checks do not independently prove a hardware observation occurred. The derivative is not a lossless backup.
