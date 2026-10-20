# Reproducing the public capture analysis

The repo contains scalar expectations and metadata fixtures, not the original photos or USB captures. Download the named `.gz` attachments from [FilmKit issue #12](https://github.com/eggricesoy/filmkit/issues/12) (X-T50, firmware 1.31) and [issue #13](https://github.com/eggricesoy/filmkit/issues/13) (X-T30, firmware 2.01). `apolozanionut` supplied the attachments. Decompress them locally; the X-T50 attachment uses a space in `Preset Save`, while the filenames on this page use an underscore. Hashes, not filenames, identify the inputs.

## Inputs and reproduced results

The SHA-256 hashes in the following table are for the decompressed captures. All four are pcapng: their headers begin with the Section Header Block magic `0A 0D 0D 0A`, followed by Interface Description and Enhanced Packet blocks.

| Input | SHA-256 | Profile writes | Recovery boundaries |
|---|---|---|---|
| `X-T50_Preset_Save.pcapng` | `267fb1204d4fdc498e99bccde241ed3692e3ef53c17c9722e4369fac101d9020` | 20 | 20 |
| `X-T30_Preset_Save_PT1.pcapng` | `55bff8cbd0c5b9779b895d4c87611f47d23acb70265020c01d2171952150863f` | 17 | 17 |
| `X-T30_Profile_Read.pcapng` | `d21bf902c9f2736aaf357c91149c61d806c68544da8c8213abd38fd1d8785e58` | 1 | 2 |
| `X-T30_Preset_Save_PT2.pcapng` | `67ed9c928f6b577b38abf596ad2e96f540b9acdbb5e157b8ae07ef8ea6b4230d` | 0 | 0 |

These counts are what the tools in this repo reproduce from those inputs. The [machine-readable expectations](../fixtures/captures/expected.json) pin the changed-cell rows, selected metadata comparisons, the X-T30 short-profile/default-fill case, and the X-T50 bank/live tail. They don't contain image pixels or DeviceInfo data.

```bash
# Use Python 3.11+ from the repository root. Replace DOWNLOAD_DIR with the folder that holds your downloads, and REPO_DIR with this repository's root.
python3 tools/ptpcap.py DOWNLOAD_DIR/X-T50_Preset_Save.pcapng --recover --profiles
python3 tools/ptpcap.py DOWNLOAD_DIR/X-T50_Preset_Save.pcapng --recover --metadata
python3 tools/ptpcap.py DOWNLOAD_DIR/X-T50_Preset_Save.pcapng --recover --json
python3 tools/verify_capture.py DOWNLOAD_DIR/X-T50_Preset_Save.pcapng DOWNLOAD_DIR/X-T30_Preset_Save_PT1.pcapng DOWNLOAD_DIR/X-T30_Profile_Read.pcapng DOWNLOAD_DIR/X-T30_Preset_Save_PT2.pcapng
```

`verify_capture.py` rejects an unknown hash rather than applying these expectations to a different recording. It doesn't download or upload anything. The JSON transaction listing includes timing, operation, parameters, response, and data lengths, without raw payloads. Profile output includes signed cells at the inspected `0x1FD` base and consecutive write diffs; it isn't a general unknown-body layout detector.

The [editor-walk transcript](x-rawstudio-editor-walk-xt50-xt30.md) explains the experiment and labels. In the X-T50 capture, tids 1819–1824 reproduce the end of the bank block and start of the live mirror: `D1A4`, `D1A5`, `D018`, `D007`, `D02E`, `D001`. `D1A5` takes approximately 16 ms there. This is evidence about that combined save, not proof that every bank save enables the live-copy option.

The additional [X-T3/X-T30 bank-path transcript](x-rawstudio-bank-availability-xt3-xt30.md) records an independent decode of two FilmKit #5 X-T3 inputs and the X-T30 Profile_Read USB-mode value. It lists separate hashes, commands, and recovery limits. The X-T3 inputs are outside the four-file `verify_capture.py` expectation set.

## Additional X-T50 Profile Read capture

The [`X-T50_Profile_Read.pcapng.gz` attachment](https://github.com/user-attachments/files/27558954/X-T50_Profile_Read.pcapng.gz) (attachment 27558954, FilmKit issue #12, firmware 1.31) was decoded separately. Its decompressed SHA-256 is `683d5f802bc1705bbf3b652a7227cf16a327b1f7bd1d3e1f740894345d8832a9`. The file is pcapng, with USBPcap link type 249. It is outside the four-file `verify_capture.py` expectation set and has no fixture or expectation.

| tid | Operation on `0xD185` | Profile bytes | numParams | IOPCode length byte | Cell 29 | Response |
|--|--|--|--|--|--|--|
| 378 | Read | 625 | 29 | 8 | absent | `0x2001` OK |
| 379 | Write | 629 | 29 | 9 | 1 | `0x2001` OK |
| 408 | Read | 625 | 29 | 9 | absent | `0x2001` OK |

All three profiles carry IOPCode `FF189504`. Independent inspection of the raw packet blocks confirmed the matching commands, complete data containers, and OK responses: frames 2917/2920/2922 for tid 378, 2923/2925/2928 for tid 379, and 3165/3168/3170 for tid 408. The write's profile bytes 625–628 are `01 00 00 00`, establishing cell 29 = `1` at base `0x1FD`. The initial read's length byte is `8`; the later read's is `9`. This contradicts a universal all-zero X-T50 tail or a universal initial length byte of `9`.

```bash
# Run from the repository root after downloading and decompressing the attachment.
python3 tools/ptpcap.py DOWNLOAD_DIR/X-T50_Profile_Read.pcapng --recover --profiles
```

The following additional check prints only the selected profile metadata, including the IOPCode length byte that `--profiles` does not currently print:

```bash
python3 -B - DOWNLOAD_DIR/X-T50_Profile_Read.pcapng <<'PY'
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, 'tools')
from ptpcap import transactions

path = Path(sys.argv[1])
expected = '683d5f802bc1705bbf3b652a7227cf16a327b1f7bd1d3e1f740894345d8832a9'
assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
for t in transactions(path, recover=True).values():
    if t['tid'] not in (378, 379, 408):
        continue
    assert t['op'] in (0x1015, 0x1016) and t['params'] == [0xD185]
    data = t['out'] if t['op'] == 0x1016 else t['in']
    assert data is not None and t['resp'] == 0x2001
    print(json.dumps({
        'tid': t['tid'], 'bytes': len(data),
        'num_params': struct.unpack_from('<H', data)[0],
        'iop_count': data[2], 'iopcode': data[3:19].decode('utf-16le'),
        'cell_29': struct.unpack_from('<i', data, 625)[0] if len(data) >= 629 else None,
        'response': hex(t['resp']),
    }))
PY
```

The decoder reports two recovery boundaries: an incomplete RAW upload at tid 374 and an incomplete JPEG download at tid 404. Those gaps do not cross the three complete profile transfers described earlier. The recording establishes accepted profile bytes and readback changes, not intact photo pixels or the purpose of cell 29. The 20 editor-walk writes and the 26 writes in the maintainers' unpublished X-T50 captures all carry `0` in cell 29; this write is the one X-T50 exception seen.

## X100V preset-save capture

The [X100V Compatibility Report in FilmKit issue #1](https://github.com/eggricesoy/filmkit/issues/1) links a [`preset_save.zip` attachment](https://github.com/user-attachments/files/26161254/preset_save.zip), ZIP SHA-256 `587c4f2f4d4ccdd9d8228b61419d52a23a21c2334ebb1d6de413b4ad4b0d3cd5`. It holds `profileSave.pcapng`, 26,896,188 bytes, SHA-256 `5cf1e4c17ca857930b44bee064303b14f2308fcfdd5208ff262576595bc3a5ab`: pcapng, all 9,576 packets with USBPcap link type 249. Decoding with recovery gives 1,290 command instances with 18 known packet gaps, 18 incomplete containers, and 18 packet-boundary resynchronizations, all in the earlier image transfers; the bank transactions in the following table have complete scalar data and OK responses. It is outside the four-file `verify_capture.py` expectation set.

All 16 `SetDevicePropValue(0xD18C)` selector writes have complete two-byte little-endian payloads and `0x2001` responses:

| Transaction IDs | Values, in order |
|--|--|
| 10096, 10122 | 6, 6 |
| 10174, 10200, 10226, 10252, 10278, 10304, 10330 | 1, 2, 3, 4, 5, 6, 7 |
| 10356, 10382, 10408, 10434, 10460, 10486, 10512 | 1, 2, 3, 4, 5, 6, 7 |

All 15 `GetDevicePropValue(0xD18D)` name reads (tids 10097, 10175, 10201, 10227, 10253, 10279, 10305, 10331, 10357, 10383, 10409, 10435, 10461, 10487, 10513) have complete data containers and `0x2001` responses. This records their presence and success; no name is reproduced.

The capture contains no `GetDeviceInfo` and no `0xD16E` access, so the model comes from the issue, and the decode establishes neither firmware nor the USB menu mode. It confirms successful selections of banks 1–7 and name reads in that session, not persistence and not the film-simulation write the issue reports. [Captured: X100V, FilmKit #1 attachment]

The following check prints only hashes, counts, transaction IDs, selector values, completeness flags, and response codes; it never prints names, photos, serials, or DeviceInfo payloads:

```sh
python3 -B - 'REPO_DIR' 'DOWNLOAD_DIR/profileSave.pcapng' <<'PY'
import collections
import hashlib
import json
from pathlib import Path
import sys

repo, capture = map(Path, sys.argv[1:3])
sys.path.insert(0, str(repo / 'tools'))
import ptpcap

with capture.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert digest == '5cf1e4c17ca857930b44bee064303b14f2308fcfdd5208ff262576595bc3a5ab'
with capture.open('rb') as stream:
    assert stream.read(4) == bytes.fromhex('0a0d0d0a')
linktypes = collections.Counter(lt for _, lt, _ in ptpcap.read_capture(capture))
assert set(linktypes) == {249}  # LINKTYPE_USBPCAP

diagnostics = []
transactions = list(ptpcap.transactions(capture, recover=True, diagnostics=diagnostics).values())
selectors = [t for t in transactions if t['op'] == 0x1016 and t['params'] == [0xD18C]]
names = [t for t in transactions if t['op'] == 0x1015 and t['params'] == [0xD18D]]
assert all(t['out'] is not None and len(t['out']) == 2 and t['resp'] == 0x2001 for t in selectors)
assert [int.from_bytes(t['out'], 'little') for t in selectors] == [6, 6, *range(1, 8), *range(1, 8)]
assert len(names) == 15 and all(t['in'] is not None and t['resp'] == 0x2001 for t in names)
device_info = [t['tid'] for t in transactions if t['op'] == 0x1001]
mode_access = [t['tid'] for t in transactions if t['op'] in (0x1014, 0x1015, 0x1016) and t['params'] == [0xD16E]]
assert not device_info and not mode_access

# Strict output allowlist: no bank names, DeviceInfo, serials, photos, or other payloads.
print(json.dumps({
    'capture_sha256': digest,
    'format': 'pcapng / LINKTYPE_USBPCAP (249)',
    'transaction_count': len(transactions),
    'recovery_enabled': True,
    'diagnostic_counts': dict(collections.Counter(d['reason'] for d in diagnostics)),
    'selectors': [{'tid': t['tid'], 'value': int.from_bytes(t['out'], 'little'),
                   'payload_bytes': len(t['out']), 'response': f'0x{t["resp"]:04X}'} for t in selectors],
    'name_reads': [{'tid': t['tid'], 'complete_data': t['in'] is not None,
                    'response': f'0x{t["resp"]:04X}'} for t in names],
    'device_info_tids': device_info,
    'usb_mode_property_tids': mode_access,
}, indent=2))
PY
```

## Recovery is explicit and heuristic

Without `--recover`, the decoder performs ordinary reassembly and reports containers left incomplete. With it, the decoder can abandon an incomplete container at a USB packet boundary when it encounters a valid new command, or a response/data header matching an already observed command on the same device. It checks type, code, length, direction where applicable, and transaction association. It doesn't search arbitrary offsets inside photo bytes for plausible headers.

The decoder never fills a known capture/USB length gap with bytes from a later packet; it quarantines subsequent bytes until it establishes a recovery boundary. Every abandonment appears as `incomplete_container` and `packet_boundary_resync` diagnostics. Capture sections/interfaces, devices, and endpoint streams remain separate, and the decoder keeps repeated transaction IDs as separate command instances. Recovery cannot establish that all packets were captured; coincidental header-like bytes are a remaining heuristic limitation. Don't turn reconstructed transaction presence into a complete byte-for-byte capture claim.

The implementation also validates pcap/pcapng lengths, interfaces, timestamp resolutions, and partial headers. USB framing follows the [USBPcap capture format](https://desowin.org/usbpcap/captureformat.html) and [Linux usbmon binary layout](https://docs.kernel.org/usb/usbmon.html#raw-binary-format-and-api). Synthetic tests exercise truncation, stream isolation, split headers, and rejection of unassociated response-like bytes.

## Metadata is recoverable even when pixels are not

The X-T50 and X-T30 Save_PT1 previews have incomplete captured GetObject data. Their sequential JPEG prefixes contain complete EXIF APP1 segments. `--metadata` extracts those segments into an in-memory metadata-only envelope and passes it to [`jpeg_recipe.py`](../tools/jpeg_recipe.py). It doesn't write the original previews to the repository.

Each result separately records `data_container_complete`, `operation_response`, `transfer_complete` (complete data plus OK response), and `pixels_validated: false`. It also identifies the anonymous capture device, session, and command instance. A complete APP1 segment and successful metadata parse don't prove intact pixels or complete transfer. The parser exports only the supported metadata allowlist; it keeps unknown enum values for those fields and doesn't dump unrelated/private fields.

Selected original-prefix metadata was independently compared using ExifTool 13.55, for example by running `exiftool -j -n -LensModulationOptimizer -InteropIndex -ColorSpace -` on the envelope through standard input:

| Body / GetObject tid | LMO raw metadata | InteropIndex | Interpreted color space |
|---|---|---|---|
| X-T50 / 1690 | 0 | R03 | Adobe RGB |
| X-T50 / 1711 | 1 | R03 | Adobe RGB |
| X-T50 / 1732 | 1 | R98 | sRGB |
| X-T30 / 483 | 1 | R98 | sRGB |
| X-T30 / 504 | 0 | R98 | sRGB |
| X-T30 / 525 | 0 | R03 | Adobe RGB |

These metadata values differ from profile LMO's `1` On / `2` Off encoding. The first pair follows a cell-21 change; the color-space pair follows a cell-22 change. [JPEG fixtures](../fixtures/jpeg/README.md) describe which values came from camera captures and which container bytes were synthesized for privacy and parser testing.

Private X-T50 captures, original test JPEGs, and uninspected public attachments are outside this reproduction claim. Their status remains in [the capture inventory](README.md) and [open questions](../docs/open-questions.md#evidence-and-provenance). In particular, this reproduction makes no new pixel-equality claim for the DR experiment.
