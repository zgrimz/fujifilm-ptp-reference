# GFX100S Monochromatic Color menu endpoints

Owner-supplied photographs show menu endpoints of −18…+18 on both the warm–cool (WC) and magenta–green (MG) axes on a GFX100S running firmware 2.13. [Owner report: GFX100S fw 2.13, menu photographs, received 2026-10-18]

## Source and method

Four photographs of the camera's **MONOCHROMATIC COLOR** screen were supplied to the project maintainer and inspected on 2026-10-18. The accompanying submission identifies the body as a GFX100S and confirms firmware 2.13; neither identification is read from a firmware screen in these photographs. The capture date, selected film simulation, and bank are not recorded. The receipt date is not a capture date.

The original JPEGs are held privately with the maintainer's hardware records, together with their file names and SHA-256 hashes, and aren't redistributed here. No public image URL was supplied. This note transcribes their menu contents.

## Photographed observations

The numbers follow the order in which the photographs were supplied, not a claimed sequence of camera operations.

| Photo | WC display | MG display | Cursor position and controls |
|--|--|--|--|
| 1 | +18 | +18 | Upper-right corner; only down and left arrows shown |
| 2 | 0 | +18 | Right edge at the vertical midpoint; up, down, and left arrows shown |
| 3 | 0 | 0 | Center; all four arrows shown |
| 4 | −18 | −18 | Lower-left corner; only up and right arrows shown |

Photos 1 and 4 show both axes at opposite corners, with the outward arrows absent. Together they establish the displayed menu endpoints. Photos 2 and 3 additionally show the positive MG endpoint with WC neutral and the neutral center.

On every screen the grid has **WARM** at the top and **G** on the right, so the positive ends are warm and green, matching the [polarity](../docs/03-encodings.md#polarity-and-use) recorded for other bodies.

## What this establishes

The GFX100S fw 2.13 menu range is −18…+18 on each axis. This is evidence about this model and firmware; it does not settle the ranges of other GFX bodies.

No USB transactions accompany these photographs. They do not test acceptance of `−180`, `0`, or `180` by `0xD193` or `0xD194`, rejection of out-of-range or off-grid writes, or persistence after saving or reconnecting. Displaying zero in the menu does not establish that a USB write of zero succeeds.

The separate earlier GFX100S diagnostic report maps WC +2 / MG −1 to `0x0014` / `0xFFF6`, supporting the property identities and ×10 encoding; see [Monochromatic Color](../docs/03-encodings.md#0xd193--0xd194-monochromatic-color). Applying that encoding to these menu endpoints predicts wire values of ±180, but the photographs contain no endpoint bytes or write responses. The [open questions](../docs/open-questions.md#bank-protocol) retain that USB test.
