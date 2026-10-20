# Bank-path evidence on the X-T3 and X-T30

This project's maintainers independently decoded the public FilmKit attachments on October 18, 2026, with `tools/ptpcap.py`. This transcript records command/response metadata and the USB-mode value only. Original captures, DeviceInfo payloads, serials, profiles, and photos are not redistributed.

## X-T3, firmware 5.11

[FilmKit issue #5](https://github.com/eggricesoy/filmkit/issues/5) explicitly identifies **USB RAW CONV./BACKUP RESTORE** and reports failed bank selects 1–7. A second reporter supplied [connection traffic](https://github.com/eggricesoy/filmkit/issues/5#issuecomment-4106779506) and the later [X RAW Studio preset-change capture](https://github.com/eggricesoy/filmkit/issues/5#issuecomment-4139084348).

| Decompressed input | SHA-256 | Decoded command instances | Recovery boundaries |
|--|--|--:|--:|
| [`xt3-connection.pcapng`](https://github.com/user-attachments/files/26168445/xt3-connection.pcapng.gz) | `3a3533fcd7dff7d240515bc5c029ad9b6767bbf41ed48824cf45b0f737dd21f6` | 15 | 0 |
| [`xt3presetchange.pcapng`](https://github.com/user-attachments/files/26290760/xt3presetchange.pcapng.gz) | `1a759e2bb237cc0355ed2b7f424e5713654ea454581b2f4f63fcc25774dbbc1f` | 142 | 4 |

The connection input captures a `GetDevicePropValue(0xD18C)` and two-byte selector writes for 1–7, then 1 again. Its incoming usbmon completion records contain no captured payload: their data length is zero and the data flag is `D`. No camera response code can be recovered from that file. The failed selections remain Published log evidence; the outbound capture corroborates the commands attempted.

The preset-change input confirms [the maintainer's original analysis](https://github.com/eggricesoy/filmkit/issues/5#issuecomment-4145133660):

| Operation | Property | Count | Responses |
|--|--|--:|--|
| SetDevicePropValue | `0xD38C` | 2 | `0x200A` |
| SetDevicePropValue | `0xD207` | 3 | `0x200A` |
| SetDevicePropValue | `0xD001` | 1 | `0x200A` |
| SetDevicePropValue | `0xD040` | 2 | `0x200A` |
| GetDevicePropValue | `0xD185` | 4 | `0x2001` |
| SetDevicePropValue | `0xD185` | 3 | `0x2001` |
| SetDevicePropValue | `0xD183` | 3 | `0x2001` |

The table lists selected operations. It omits routine status reads and one OK write to `0xD406`, a standard MTP host property.

It also reads `0xD16E = 6` with OK responses at tids 4 and 29. Its DeviceInfo summaries identify X-T3 fw 5.11, 27 operations, and 168 advertised properties, with no `0xD18C`–`0xD1A5`. Transaction IDs repeat across sessions; the decoder preserves command instances separately. These failed auxiliary writes are not bank-selector tests and do not establish what `0xD38C` means.

The decoder reports one known packet gap, four incomplete containers, and four recovery boundaries for this input. Those limits prevent a complete-transfer or pixel-integrity claim. The command/response evidence supports the practical result: direct bank editing did not work in the documented runs, while conversion-profile operations and starts succeeded. The separately published settings-backup path remains the working bank route on this body.

## X-T30, firmware 2.01

The [issue #13 inline FilmKit log](https://github.com/eggricesoy/filmkit/issues/13) reports failed selection of slot 1. That failure is not present in the three captures decoded for [the editor walk](x-rawstudio-editor-walk-xt50-xt30.md): none contains an operation on `0xD18C`–`0xD1A5`.

`X-T30_Profile_Read.pcapng`, SHA-256 `d21bf902c9f2736aaf357c91149c61d806c68544da8c8213abd38fd1d8785e58`, reads `0xD16E = 6` with OK responses at tids 10 and 40. This establishes **USB RAW CONV./BACKUP RESTORE** in that captured session directly. Its DeviceInfo summaries identify fw 2.01, 27 operations, and zero advertised properties; `0xD185` reads/writes and a `0xD183` start still succeed. There are 66 command instances, two known packet gaps, two incomplete containers, and two recovery boundaries.

Preset_Save_PT1 has 17 profile writes and conversion starts, with no bank-block writes. Preset_Save_PT2 has only eight `0xD36A`/`0xD36B` reads. Their hashes and pinned checks remain in [capture reproduction](reproduction.md). This establishes no successful bank operation in the supplied evidence, not an additional captured slot refusal.

## Reproduce

Download and decompress the linked attachments outside the repository. From its root, using Python 3.11+:

```bash
python3 tools/ptpcap.py DOWNLOAD_DIR/xt3-connection.pcapng --recover --json
python3 tools/ptpcap.py DOWNLOAD_DIR/xt3presetchange.pcapng --recover --json
python3 tools/ptpcap.py DOWNLOAD_DIR/X-T30_Profile_Read.pcapng --recover --json
```

The JSON reports omit payloads. To inspect only the USB-mode scalar, without exporting DeviceInfo or photo bytes:

```bash
python3 - DOWNLOAD_DIR/xt3presetchange.pcapng DOWNLOAD_DIR/X-T30_Profile_Read.pcapng <<'PY'
import sys
sys.path.insert(0, 'tools')
import ptpcap
for path in sys.argv[1:]:
    for t in ptpcap.transactions(path, recover=True).values():
        if t['op'] == 0x1015 and t['params'] == [0xD16E]:
            data = t['in']
            if data is not None and len(data) in (2, 4):
                print(t['transaction_key'], int.from_bytes(data, 'little'),
                      None if t['resp'] is None else hex(t['resp']))
PY
```

The two X-T3 inputs are an additional decode; they are not among the four inputs accepted by `verify_capture.py`'s pinned editor-walk expectations.
