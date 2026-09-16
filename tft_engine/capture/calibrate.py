"""Calibrate shop-card templates from a labeled screenshot.

The in-game card (art band + name + cost + trait rows) is a deterministic
render per champion on a given client language/resolution — one labeled frame
per set yields exact-match templates that survive noisier reference-art
approaches. Templates live in data/card_templates/{set}/ and are matched
whole-card, so they outrank the approximate cdragon icons when both exist.

    python -m tft_engine.capture.calibrate shot.png \\
        Fiddlesticks Soraka Rengar Yorick Tristana --set 18
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from .icons import icon_filename
from .match import SHOP_CARD_LEFT, SHOP_CARD_STRIDE

# Full card interior: art band + name/cost row (fractions of image).
CARD_TOP = 0.840
CARD_BOTTOM = 0.985
CARD_W = 0.118


def card_box(i: int) -> tuple[float, float, float, float]:
    left = SHOP_CARD_LEFT + i * SHOP_CARD_STRIDE
    return (left, CARD_TOP, left + CARD_W, CARD_BOTTOM)


def calibrate_shop(
    image_path: str | Path,
    names: list[str],
    set_no: int,
    out_dir: Path,
) -> dict[str, Path]:
    if len(names) != 5:
        raise ValueError(f"expected 5 shop card names, got {len(names)}")
    img = Image.open(image_path)
    w, h = img.size
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for i, name in enumerate(names):
        l, t, r, b = card_box(i)
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
