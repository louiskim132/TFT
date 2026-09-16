"""Calibrate shop-card templates from a labeled screenshot.

The discriminating region is the card's bottom strip (name text + cost icon) —
a deterministic render per champion per client language. Templates are the
binarized strip only, so they survive framing drift between pastes.

Two input shapes are supported, auto-detected by aspect ratio:
- full frame:  cards live in the bottom shop band (SHOP_* constants)
- shop bar:    the paste is just the shop bar (BAR_* constants)

    python -m tft_engine.capture.calibrate shot.png \\
        Fiddlesticks Soraka Rengar Yorick Tristana --set 18

Use '-' for empty/unidentified slots.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from .icons import icon_filename

# Card column geometry — full-frame (fraction of image) ...
SHOP_CARD_LEFT = 0.286
SHOP_CARD_STRIDE = 0.121
CARD_W = 0.118
# ... and shop-bar crop (fraction of the bar image)
BAR_LEFT = 0.178
BAR_STRIDE = 0.165
BAR_W = 0.158
BAR_MIN_ASPECT = 3.5

# Generous region holding the name+cost strip: bbox-normalization in match.py
# crops to the glyphs, so this window only needs to contain the name row.
BAR_STRIP_TOP = 0.83
BAR_STRIP_BOTTOM = 0.98
FRAME_STRIP_TOP = 0.94
FRAME_STRIP_BOTTOM = 0.985
STRIP_INSET = 0.0


def is_shop_bar(img: Image.Image) -> bool:
    w, h = img.size
    return w / h > BAR_MIN_ASPECT


def bar_card_columns(img: Image.Image) -> list[tuple[float, float]] | None:
    """Per-card interior x-ranges, found from the dark separator lines in the
    name-row band. Paste framing drifts ±10px between screenshots, so the
    boundaries are detected per image rather than assumed constant."""
    import numpy as np

    a = np.asarray(img.convert("L"), dtype=np.float32) / 255
    h, w = a.shape
    band = a[int(0.84 * h) : int(0.97 * h)]
    colmean = band.mean(axis=0)
    seps: list[float] = []
    for k in range(5):
        exp = BAR_LEFT + k * BAR_STRIDE
        lo, hi = int((exp - 0.03) * w), int((exp + 0.03) * w)
        if lo < 0 or hi > w:
            return None
        seps.append((lo + int(np.argmin(colmean[lo:hi]))) / w)
    # card 5's right edge: image edge (the cost digit can sit past the last
    # separator line), so derive it from the left edge + card width.
    seps.append(min(0.999, seps[4] + BAR_W + 0.01))
    border = 4 / w
    return [(seps[i] + border, seps[i + 1] - border) for i in range(5)]


def strip_box(
    i: int,
    bar: bool,
    columns: list[tuple[float, float]] | None = None,
) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the i-th card's name strip, fractions."""
    if bar:
        top, bottom = BAR_STRIP_TOP, BAR_STRIP_BOTTOM
        if columns is not None:
            return (columns[i][0], top, columns[i][1], bottom)
        left, stride, width = BAR_LEFT, BAR_STRIDE, BAR_W
    else:
        left, top, bottom = SHOP_CARD_LEFT, FRAME_STRIP_TOP, FRAME_STRIP_BOTTOM
        stride, width = SHOP_CARD_STRIDE, CARD_W
    l = left + i * stride + STRIP_INSET
    return (l, top, l + width - 2 * STRIP_INSET, bottom)


def calibrate_shop(
    image_path: str | Path,
    names: list[str],
    set_no: int,
    out_dir: Path,
) -> dict[str, Path]:
    if len(names) != 5:
        raise ValueError(f"expected 5 shop card names, got {len(names)}")
    img = Image.open(image_path)
    bar = is_shop_bar(img)
    columns = bar_card_columns(img) if bar else None
    w, h = img.size
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for i, name in enumerate(names):
        if name == "-":  # empty or unidentified slot
            continue
        l, t, r, b = strip_box(i, bar, columns)
        crop = img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        path = out_dir / icon_filename(name)
        crop.save(path)
        saved[name] = path
    return saved


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tft_engine.capture.calibrate")
    ap.add_argument("image")
    ap.add_argument("names", nargs=5, help="shop card names, left to right")
    ap.add_argument("--set", dest="set_no", type=int, default=18)
    ap.add_argument("--out", default=None, help="template dir")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else Path("data/card_templates") / str(args.set_no)
    saved = calibrate_shop(args.image, args.names, args.set_no, out)
    for name, path in saved.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
