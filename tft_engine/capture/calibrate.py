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


def bar_name_boxes(img: Image.Image) -> list[tuple[float, float, float, float] | None]:
    """Per-slot bounding box around the card's name glyphs.

    A generous fixed window per slot (covers ~±15px of paste drift) is
    searched for white text — the name banner is colored, so a min-channel
    mask isolates glyphs. Returns None for slots with no text (empty)."""
    import numpy as np

    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    boxes: list[tuple[float, float, float, float] | None] = []
    for k in range(5):
        # name sits at the card's left, cost icon far right — the window ends
        # before the cost digit so only the name glyphs are captured.
        l0 = int((0.172 + k * BAR_STRIDE) * w)
        r0 = l0 + int(0.118 * w)
        t0, b0 = int(0.82 * h), int(0.975 * h)
        mask = rgb[t0:b0, l0:r0].min(axis=2) > 0.58
        if int(mask.sum()) < 12:
            boxes.append(None)
            continue
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        # drop the cost icon if it still leaked in at the right edge
        boxes.append(
            (
                (l0 + cols[0]) / w - 0.004,
                (t0 + rows[0]) / h - 0.01,
                (l0 + cols[-1]) / w + 0.004,
                (t0 + rows[-1]) / h + 0.012,
            )
        )
    return boxes


def strip_box(
    i: int,
    bar: bool,
    name_boxes: list[tuple[float, float, float, float] | None] | None = None,
) -> tuple[float, float, float, float] | None:
    """(left, top, right, bottom) of the i-th card's name strip, fractions.
    Bar mode uses the detected name-glyph box; returns None for empty slots."""
    if bar:
        if name_boxes is not None:
            return name_boxes[i]
        top, bottom = BAR_STRIP_TOP, BAR_STRIP_BOTTOM
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
    name_boxes = bar_name_boxes(img) if bar else None
    w, h = img.size
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for i, name in enumerate(names):
        if name == "-":  # empty or unidentified slot
            continue
        box = strip_box(i, bar, name_boxes)
        if box is None:
            continue  # no name glyphs found at this slot (likely empty)
        l, t, r, b = box
        crop = img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        base = icon_filename(name)
        path = out_dir / base
        k = 2  # keep a variant per observation; min-over-variants at match time
        while path.exists():
            path = out_dir / f"{base[:-4]}__{k}.png"
            k += 1
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
