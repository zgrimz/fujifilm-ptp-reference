# Bank write timing

How long a camera takes to accept a bank write, from every published trace that carries durations: the maintainers' 31 X-T50 client traces and the GFX100S owner's 9 distinct client traces. It reconciles the [transport chapter's timing table](../docs/01-transport.md#timing) with them. To recompute every figure on this page from the public ledgers, run:

```bash
python3 -B tools/write_timing.py
```

The X-T50 traces are the 29 [client-trace packages](xt50-client-traces/README.md) and the [12:50](xt50-20261019-125007/README.md) and [14:05](xt50-20261019-140542/README.md) client-report packages, all firmware 1.32. The GFX100S traces are the ten [owner-report packages](README.md#available-owner-report-packages) at firmware 1.32 and 2.13; the 21:16 trace on 2026-09-17 is the first 171 rows of the 21:51 trace, so it is counted once. Every duration is host-measured: the time from the maintainers' iOS client handing a command to ImageCaptureCore to its completion.

## The figures

A write that takes 200 ms or more is counted as slow. In these traces no accepted write falls between 161 and 265 ms, so the boundary doesn't decide which side any write lands on.

| Writes and reads | X-T50, 31 traces | GFX100S, 9 traces |
|---|---|---|
| Bank name (`0xD18D`), accepted | 47: 41 at 76–114 ms, median 102; 6 at 266–275 ms | 4: 2 at 103 ms; 2 at 325 and 329 ms |
| Bank settings `0xD18E`–`0xD1A4`, accepted | 922: 882 at 97–160 ms, median 118; 40 at 288–318 ms (4.3%) | 81: 76 at 67–135 ms, median 118; 5 at 344–356 ms (6.2%) |
| White balance (`0xD199`) alone | 47: 43 at 102–145 ms, median 129; 4 at 291–300 ms | 4: 78–120 ms |
| Live Image Size (`0xD1A5`), accepted | 40 at 29–49 ms | none accepted |
| Property reads, except the `0xD185` profile | 8,149, the slowest 60 ms | 1,556, the slowest 90 ms |

[Measured: X-T50 fw 1.32, the maintainers' iOS client] [Owner report: GFX100S fw 2.13, the same client]

The one wire-level measurement is X RAW Studio's bank save in the [FilmKit #12 capture](../captures/x-rawstudio-bank-save-xt50.md): a 232 ms name write and a 246 ms white-balance write, against a 55–246 ms span for its accepted bank-setting writes. [Captured: X-T50 fw 1.31, FilmKit #12 capture]

## What they show

- A name write takes as long as a bank-setting write. The fast name writes on each body fall inside its bank-setting range, and the two empty-name writes, `00` and `010000`, took 76 and 100 ms. The maintainers' originals also show fast and slow name writes across the same range of name lengths, from the shortest to the longest name written; the ledgers omit lengths, so that comparison isn't checkable from the packages.
- Some bank writes take much longer, about one in 20: 170–200 ms longer on the X-T50, and 226–238 ms longer on the GFX100S. The slow writes fall on many properties, the name among them, with no property consistently slow. The earlier "~230–325 ms" name-write figure combined two such writes: the capture's 232 ms and the GFX100S restore's 325 ms. The capture's 246 ms white-balance write fits the same pattern. On the X-T50, white balance takes a median of 129 ms when it isn't slow, like any other bank setting.
- Reads don't slow down. None of 9,705 property reads took 100 ms. A camera task that blocked every command for that long would have fallen on some read pass, so whatever causes the slow writes affects writes. Whether a write triggers it, for instance by committing the bank to storage, isn't established.
- The live `0xD1A5` write is quicker than any bank setting, 29–49 ms, as X RAW Studio's live writes are on the wire (4–18 ms).

## What upstream projects do

No upstream project publishes a measured duration for any bank write. Several insert fixed delays, without a measurement behind them: FilmKit and grawji wait 100 ms after a select, and FilmKit then writes the name. Filmcase waits 50 ms around every read and write; its first version called 50 ms before and 200 ms after each setting write a requirement, and a later commit cut the 200 ms to 50 ms. fujifilm-ptp-recipes recommends about 100 ms after a select and reports 0 ms between writes on an X-H2. [Errata](../docs/errata.md#a-settle-delay-after-selecting-a-bank-is-a-precaution-not-a-measured-need) keeps the settle-delay claims with their sources.

## For a client

Expect an occasional bank write of about 300 ms, and don't read it as a failure; a timeout of seconds is far above it. These traces don't show whether a pause between writes changes the rate of slow writes, because they don't record host time between commands.
