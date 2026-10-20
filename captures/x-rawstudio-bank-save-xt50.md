# X RAW Studio saving a bank — X-T50

Source: `X-T50_Preset Save.pcapng`, attached to [FilmKit issue #12](https://github.com/eggricesoy/filmkit/issues/12). Windows, USBPcap, Fujifilm X RAW Studio saving a preset named `SAVEPCAP` to C1 on an X-T50 running firmware 1.31. Decoded with [`tools/ptpcap.py`](../tools/README.md).

## Transcript

Transaction IDs 1770–1842. The final selector write (tid 1795) takes 4.291 ms; the name command starts 4.676 ms after that selector command, only 0.385 ms after its response. This establishes no substantial settling pause in this save. The named write durations in the following transcript are command-to-response latencies; the live-write timing table is in the editor-walk transcript.

```
Set D18C=1 → OK            4 ms   select C1; no selector read-back
Get D18D, D18E…D1A4 → OK          read the bank first; order D199, D19C, D19A, D19B;
                                  D1A5 is never read
Set D18C=1 → OK                   select again before writing
Set D18D "SAVEPCAP" → OK   232 ms NAME FIRST: a name write, not an established commit
Set D18E=0009 → OK          79 ms Image Size L 1:1, accepted on C1
Set D18F=0002 → OK                FINE
Set D190=0064 → OK                DR100
Set D191=0000 → 0x201C            D-Range Priority Off refused (presumably bank at base ISO)
Set D192=000B → OK                Classic Chrome
Set D193=0000 → 0x201C            mono WC on a color simulation
Set D194=0000 → 0x201C            mono MG on a color simulation
Set D195…D198 → OK
Set D199=0004 → OK         246 ms Daylight
Set D19C=0000 → 0x201C   5.283 ms Kelvin 0 while Daylight is selected; cause not isolated (tid 1809)
Set D19A, D19B, D19D, D19E, D19F, D1A0, D1A1, D1A2 → OK
Set D1A3=0001, D1A4=0001 → OK      85 ms  the last bank setting
Set D1A5=0009 → OK          16 ms  the FIRST LIVE WRITE: X RAW Studio's live Image Size, with D18E's value
Set D018, D007, D02E, D001, D104, D031, D023, D029, D030, D189, 5005, D017,
    D00B, D00C, D320, D321, D008, 5015, D01C, D032, D34D, D00A → OK, 4–18 ms each
… 1.7 s later: reselect C1, re-read it (D18E now 0009) and every other bank
```

The 23 live writes carry, one for one and in the bank write's order, the values just written to the bank. For the timing table and the full mirror, see [the editor-walk transcript](x-rawstudio-editor-walk-xt50-xt30.md#the-live-write-after-a-bank-save-issue-12).

## What it shows

- Order: name first, then ascending, except `D19C` straight after `D199`. There is no `GetDevicePropDesc` anywhere (consistent with the X-T50 refusing it), no retries, no read-back of the selector, and no substantial settling pause between select and name.
- This captured save attempts all 23 bank settings and continues past refusals. The camera refused four writes with `0x201C`. The two toning refusals are consistent with the color simulation. The Kelvin write used `0` while Daylight was selected, so it doesn't isolate an invalid value from a white balance mode restriction; see [Kelvin](../docs/03-encodings.md#0xd19c-color-temperature). The fourth refusal, `D191`, is consistent with the D-Range Priority ISO gate, but the bank ISO wasn't independently recorded in this capture; see [ISO gating](../docs/04-custom-slots.md#iso-gating).
- Timing: accepted bank-setting writes span 55–246 ms. Three refusals take about 46 ms; the Kelvin refusal (`D19C`, tid 1809) takes 5.283 ms. The separate name write takes about 232 ms and white balance about 246 ms; the live writes take 4–18 ms.
- `D18E` is writable on C1 of an X-T50 (`0009` stuck). A refusal might come from a bank state such as Sports Finder Mode; a refusal doesn't by itself identify the cause.
- `D1A5` isn't a bank setting. X RAW Studio writes it straight after `D1A4` with `D18E`'s value, in live-write time, never reads it with the bank, and follows it with the other 22 live twins. The live write carries the same value as the bank write; X RAW Studio doesn't read `D1A5` back here, so this capture can't establish equality in subsequent bank reads.
- Values: `D18E` 7 = L 3:2 and 9 = L 1:1 (from the author's X RAW Studio screen); `D18F` 2 = **FINE**. The bank held `D18F = 3` before the save. The camera accepted the four live writes whose bank twins it refused.

The live mirror described here is the branch present in this captured combined save. X RAW Studio also offers separate **CAMERA SETTING** and **CAMERA CUSTOM SETTING** choices; for the optional branch, see [Live shooting properties](../docs/02-properties.md#live-shooting-properties). For recovery and metadata completeness, see [Reproducing the public capture analysis](reproduction.md).
