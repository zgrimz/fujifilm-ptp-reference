# Tools

Use Python 3.11 or later, and run every Python command with `python3 -B` (or `PYTHONDONTWRITEBYTECODE=1`): the scripts and tests import sibling modules, and `check_reference.py` reports the `__pycache__` they'd otherwise write. JPEG extraction and capture decoding use the standard library and never open a camera. `bankprobe.py` loads USB dependencies only for hardware commands. Tests are offline; `validate_evidence.py` and `tests/test_evidence.py` need the packages in `requirements-test.txt`.

## JPEG recipe extraction

```bash
python3 tools/jpeg_recipe.py JPEG_FILE
python3 tools/jpeg_recipe.py JPEG_FILE --wb-shift-scale times20
```

[`jpeg_recipe.py`](jpeg_recipe.py) emits JSON with raw supported tags, normalized recipe fields, interpretation provenance, warnings, and explicit unknown/unresolved states. It doesn't create a PTP write list or fill absent fields with defaults. WB scaling defaults to unresolved; use an explicit scale only when the input's evidence supports it. For the format, mappings, and fixtures, see [Reading recipe settings from a JPEG](../docs/10-jpeg-recipes.md) and [JPEG fixture provenance](../fixtures/jpeg/README.md).

## PTP capture decoding

```bash
python3 tools/ptpcap.py CAPTURE_FILE
python3 tools/ptpcap.py CAPTURE_FILE --all
python3 tools/ptpcap.py CAPTURE_FILE --recover --profiles
python3 tools/ptpcap.py CAPTURE_FILE --recover --metadata
python3 tools/ptpcap.py CAPTURE_FILE --recover --json
python3 tools/verify_capture.py PUBLIC_CAPTURE_FILE
```

Default text output shows selector/name/bank/live-Image-Size operations in `D18C`–`D1A5`, plus non-OK responses. That display range doesn't make `D1A5` a bank setting. Text output includes elapsed time, command gaps, transaction IDs, operation/property, response, and response time. It prints raw values only for the numeric `D18E`–`D1A5` allowlist; it shows names, DeviceInfo, object transfers, and other payloads by length.

`--profiles` exports complete captured profile reads/writes whose bytes after the fixed `0x1FD` base form whole four-byte cells, plus signed cells and consecutive-write diffs. It skips other shapes, including rawji's constructed 632-byte form with three trailing padding bytes; absence from this report does not prove that no profile was transferred. `--metadata` parses complete EXIF APP1 segments available in JPEG prefixes, even where the captured object transfer is incomplete; it always reports `pixels_validated: false`. `--json` emits transaction summaries without payload bytes. JSON output includes the input hash and recovery diagnostics.

Supported framing: classic pcap and pcapng, USBPcap link type 249, and usbmon link types 189/220. The decoder isolates streams by capture section/interface, device, and endpoint, and reassembles headers and payloads that span packets. `--recover` enables a bounded heuristic at packet boundaries, with every abandoned container reported. It can't recreate missing bytes or prove pixel integrity. `verify_capture.py` checks the four public FilmKit captures against pinned expectations and refuses any other hash. For those inputs (which issue attachments to download and how to decompress them), reproduction commands, exact hashes, and limitations, see [Reproducing the public capture analysis](../captures/reproduction.md).

## Bank research probe

[`bankprobe.py`](bankprobe.py) talks PTP in **USB RAW CONV./BACKUP RESTORE** mode. Hardware commands require `pyusb` and libusb (for example, `python3 -m pip install pyusb` and `brew install libusb` on macOS). Set the camera's auto power off to **OFF**. Before connecting, quit any application that already owns the PTP interface. Connecting third-party software might void your camera's warranty; see [Warranty](../README.md#warranty).

```bash
python3 tools/bankprobe.py selftest                  # no USB imports/discovery
python3 tools/bankprobe.py info
python3 tools/bankprobe.py dump --out bankprobe-banks.json  # name + 23 settings, no live copy
python3 tools/bankprobe.py backup --bank 7           # save one bank to backups/
python3 tools/bankprobe.py sweep --bank 7            # read, wait for ONE menu change, read again, diff
python3 tools/bankprobe.py --list-tests
python3 tools/bankprobe.py test filmsim d1a3 --bank 7
python3 tools/bankprobe.py test name-last --bank 7 --auto-update off
python3 tools/bankprobe.py probe --bank 7 D193=0 D193=5
python3 tools/bankprobe.py restore backups/BACKUP_FILE.json --bank 7
python3 tools/bankprobe.py guided --bank 7 --other-bank 6
python3 tools/bankprobe.py guided --set confirm --bank 7 --other-bank 6
```

For named trials run through `test` or `guided`, use `--camera-state` to supply an operator-checked description of shooting bank, ISO, format, and relevant modes, and `--auto-update on|off|unknown` to record the **AUTO UPDATE CUSTOM SETTING** observation. If you omit either value, the tool asks for it. These prompts and structured context records apply only to those trials; `probe` and `restore` don't collect them. The tool can't discover the **AUTO UPDATE CUSTOM SETTING** state automatically. Unsaved/live-state trials require it confirmed off. A persistence conclusion with unknown setup state remains limited.

The `dr-placeholder` menu trial records both DR and priority through an Off/On/Off sequence. It requires readback confirmation that priority became active and returned to Off before interpreting the DR change. DR100 → `0xFFFF` → DR100 is consistent with a temporary placeholder, but does not prove how the camera stores the setting. A final `0xFFFF`, an unconfirmed priority transition, or a missing reading leaves the interpretation inconclusive.

The write guard captures immutable originals before a trial: all 23 bank settings, the exact PTP name bytes, and the selector. If it can't recover the required originals, it refuses the trial. This is deliberately conservative: a body that can't read one of these fields might be readable by other commands but isn't eligible for this tool's write trials. Only an explicitly targeted live test backs up and restores `D1A5`, in a separate namespace.

Generic bank probes validate the whole write list before selection and permit only name/settings `D18D`–`D1A4`. A probe can't include selector or live writes in that list. The tool refuses a probe that would change remembered grain-Off variants 6/7: its restore implementation doesn't use the [size-then-Off sequences demonstrated on an X-T50 and a GFX100S](../docs/03-encodings.md#0xd195-grain-effect). This is a tool limitation, not evidence that those values cannot be reconstructed. `--no-restore` keeps changes only after verified success; failure or interruption still invokes cleanup.

Write trials save version-2 snapshots to `backups/`. Restoration rejects legacy/live-containing snapshots rather than silently changing their meaning; migrate such files explicitly after reviewing scope and identity. The `restore` command targets the same bank, checks model/firmware, and first snapshots the current state for rollback. Matching metadata doesn't prove the same physical camera. The tool asks for same-camera confirmation on read recovery, and a metadata mismatch blocks further writes.

Cleanup runs after failures/skips as well as normal completion, reselects and verifies each target, follows dependency rules, restores names, and compares fresh state. Exact, semantic-only, mismatched, and unavailable results remain distinct. A successful cleanup read doesn't prove power-cycle persistence. The tool never automatically replays uncertain setting writes after a lost connection.

Some experiments ask the operator to change ISO, format, modes, the active shooting bank, or menu settings outside the captured 23 fields. Those changes remain outside automatic cleanup, and the operator must restore them. Read/menu sweeps don't write recipe fields, but selecting a bank for reading writes the selector. Use a bank you can spare: no known operation in this property protocol restores unknown empty-bank state; camera-menu **ERASE** is separate.

Runs produce local JSON logs, transcripts, and recovery files. They can contain bank names and recipe contents even though DeviceInfo serials are omitted. `.gitignore` excludes the default `bankprobe-*.json` and `bankprobe-*.txt` filenames and the `backups/` directory. Custom `--out` or `--log` paths outside those patterns aren't automatically excluded. Check custom outputs before publishing, and review/sanitize all run output before sharing. Follow the [contribution guidance](../CONTRIBUTING.md).

## Write timing

```bash
python3 -B tools/write_timing.py
python3 -B tools/write_timing.py --json
```

[`write_timing.py`](write_timing.py) recomputes the bank-write timing figures that the [transport chapter](../docs/01-transport.md#timing) and the [write-timing note](../evidence/write-timing.md) cite: name, bank-setting, white balance, and live Image Size writes, and property reads, for each body. It reads only the published client-trace ledgers and never opens a camera or an original. A trace that is an exact prefix of a later trace of the same body is counted once, and a write of 200 ms or more counts as slow. `test_client_trace_packages.py` checks the figures the record cites.

## Evidence validation and the offline checks

[`validate_evidence.py`](validate_evidence.py) checks an observation report against the [report schema](../evidence/report-schema.md); [`check_reference.py`](check_reference.py) checks the record's links, anchors, table widths, and Python syntax, and reports stray captures or caches. The design patterns a client should follow are prose, in [client implementation](../docs/11-client-implementation.md).

The synthetic [test vectors](../fixtures/conformance/README.md) exercise the tools themselves: `bankprobe.py`'s response, stream, and string parsing and its write blocking after a lost reply, and `jpeg_recipe.py`'s decoding and JSON round trip. `test_conformance.py` checks their integrity, and each case records the checks that execute it; see the [coverage table](../fixtures/conformance/README.md#what-runs-here). `cases.json` holds command-outcome and field-verification examples for adapting to a client's own tests.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python -B tools/bankprobe.py selftest
.venv/bin/python -B tools/validate_evidence.py evidence/example.synthetic.json
.venv/bin/python -B tools/check_reference.py
```

The JPEG tests can additionally use ExifTool 13.55 when installed; their fixture manifests state what was independently checked. Public-capture verification is a separate explicit command because raw captures aren't bundled. No ordinary test requires a camera or performs a network request.
