"""Template matching: locate shop card portraits and identify them.

Two template sources:
- card templates (data/card_templates/{set}/) — cropped in-game card interiors
  from a labeled frame; deterministic renders, so MSE is near-exact.
- cdragon square icons (data/icons/{set}/) — approximate fallback; the in-game
  art is a different crop, so these rank poorly and serve mostly for debugging.

Geometry is expressed as fractions of image size so it scales across
resolutions; constants were measured on a 1024x576 planning-phase frame.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

# Shop band geometry (fractions of image).
SHOP_CARD_LEFT = 0.286
SHOP_CARD_STRIDE = 0.121

# Full-card interior (calibrated templates): art + name/cost/traits.
CARD_W = 0.118
CARD_TOP = 0.840
CARD_BOTTOM = 0.985

# Art-band only (cdragon icon fallback).
SHOP_PORTRAIT_W = 0.113
SHOP_PORTRAIT_TOP = 0.840
SHOP_PORTRAIT_H = 0.095

ICON_SIZE = 64
# A match below this MSE is treated as reliable; above it the name is a guess.
CONFIDENT_MSE = 0.02


@dataclass(frozen=True)
class Match:
    name: str | None
    mse: float
    runner_up: str | None
    runner_up_mse: float

    @property
    def confident(self) -> bool:
        return self.mse < CONFIDENT_MSE


class IconLibrary:
    """Loads a directory of templates. `mode` selects which screen region each
    template depicts: 'card' = calibrated full card interior, 'icon' = cdragon
    square portrait."""

    def __init__(self, icon_dir: str | Path, mode: str = "icon") -> None:
        self.mode = mode
        self.templates: dict[str, np.ndarray] = {}
        for path in sorted(Path(icon_dir).glob("*.png")):
            arr = np.asarray(
                Image.open(path).convert("RGB").resize((ICON_SIZE, ICON_SIZE)),
                dtype=np.float32,
            )
            self.templates[path.stem] = arr / 255.0

    @property
    def slot_box(self) -> tuple[float, float, float, float, float]:
        if self.mode == "card":
            return (SHOP_CARD_LEFT, CARD_TOP, CARD_W, CARD_BOTTOM - CARD_TOP)
        return (
            SHOP_CARD_LEFT,
            SHOP_PORTRAIT_TOP,
            SHOP_PORTRAIT_W,
            SHOP_PORTRAIT_H,
        )

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
    left0, top, cw, ch = lib.slot_box
    out: list[Match] = []
    for i in range(5):
        left = left0 + i * SHOP_CARD_STRIDE
        out.append(lib.match(_crop_fraction(img, (left, top, left + cw, top + ch))))
    return out


if __name__ == "__main__":
    import sys

    shot = Image.open(sys.argv[1])
    src = sys.argv[2] if len(sys.argv) > 2 else "data/card_templates/18"
    mode = "card" if "card_templates" in src else "icon"
    library = IconLibrary(src, mode=mode)
    for slot, m in enumerate(detect_shop(shot, library), 1):
        flag = "" if m.confident else "  [low confidence]"
        print(
            f"slot {slot}: {m.name} (mse={m.mse:.4f})"
            f"  runner-up {m.runner_up} ({m.runner_up_mse:.4f}){flag}"
        )
