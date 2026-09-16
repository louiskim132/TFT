"""Template matching: locate shop card portraits and identify them against the
cached icon library.

Geometry is expressed as fractions of image size so it scales across
resolutions; constants were measured on a 1024x576 planning-phase frame and
may need a second row of calibration for other aspect ratios.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# Shop band geometry (fraction of image). Five cards; the card's top band is
# the champion's square splash horizontally stretched to card width (trait
# text overlays its lower-left, so we match the top portion only).
SHOP_CARD_LEFT = 0.286
SHOP_CARD_STRIDE = 0.121
SHOP_PORTRAIT_W = 0.113
SHOP_PORTRAIT_TOP = 0.840
SHOP_PORTRAIT_H = 0.050

ICON_SIZE = 64


@dataclass(frozen=True)
class Match:
    name: str | None
    mse: float
    runner_up: str | None
    runner_up_mse: float


class IconLibrary:
    def __init__(self, icon_dir: str | Path, size: int = ICON_SIZE) -> None:
        self.size = size
        self.templates: dict[str, np.ndarray] = {}
        for path in sorted(Path(icon_dir).glob("*.png")):
            arr = np.asarray(
                Image.open(path).convert("RGB").resize((size, size)),
                dtype=np.float32,
            )
            self.templates[path.stem] = arr / 255.0

    def match(self, crop: np.ndarray) -> Match:
        best, second = None, None
        best_mse, second_mse = float("inf"), float("inf")
        for name, tpl in self.templates.items():
            mse = float(np.mean((crop - tpl) ** 2))
            if mse < best_mse:
                second, second_mse = best, best_mse
                best, best_mse = name, mse
            elif mse < second_mse:
                second, second_mse = name, mse
        return Match(best, best_mse, second, second_mse)


def _crop_fraction(img: Image.Image, box: tuple[float, float, float, float]) -> np.ndarray:
    w, h = img.size
    l, t, r, b = box
    return np.asarray(
        img.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        .convert("RGB")
        .resize((ICON_SIZE, ICON_SIZE)),
        dtype=np.float32,
    ) / 255.0


def detect_shop(img: Image.Image, lib: IconLibrary) -> list[Match]:
    """One Match per shop slot (5 slots, left to right)."""
    out: list[Match] = []
    for i in range(5):
        left = SHOP_CARD_LEFT + i * SHOP_CARD_STRIDE
        box = (
            left,
            SHOP_PORTRAIT_TOP,
            left + SHOP_PORTRAIT_W,
            SHOP_PORTRAIT_TOP + SHOP_PORTRAIT_H,
        )
        out.append(lib.match(_crop_fraction(img, box)))
    return out


if __name__ == "__main__":
    import sys

    shot = Image.open(sys.argv[1])
    library = IconLibrary(sys.argv[2] if len(sys.argv) > 2 else "data/icons/18")
    for slot, m in enumerate(detect_shop(shot, library), 1):
        print(
            f"slot {slot}: {m.name} (mse={m.mse:.4f})"
            f"  runner-up {m.runner_up} ({m.runner_up_mse:.4f})"
        )
