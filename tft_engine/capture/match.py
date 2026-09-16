"""Template matching: identify shop cards by their name strips.

Templates are the card's bottom strip (name + cost), binarized and normalized
to the bright-pixel bounding box — Korean text matches by glyph shape, so no
OCR is needed, and bbox-normalization makes matching immune to the few-pixel
framing drift between screenshot pastes.

- card templates (data/card_templates/{set}/): calibrated strips, near-exact
- cdragon icons (data/icons/{set}/): art fallback, approximate — debugging aid
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .calibrate import bar_card_columns, is_shop_bar, strip_box

STRIP_W, STRIP_H = 96, 24
ICON_SIZE = 64

# Binarized-strip MSE after bbox normalization: same unit lands <~0.03;
# different units diverge >~0.06. Between is a "probable" grey zone.
CONFIDENT_MSE = 0.045
# An empty slot's strip has no name/cost glyphs — almost no bright pixels.
EMPTY_VAR = 0.002
EMPTY_BRIGHT_PX = 20


@dataclass(frozen=True)
class Match:
    name: str | None
    mse: float
    runner_up: str | None
    runner_up_mse: float
    empty: bool = False

    @property
    def confident(self) -> bool:
        return not self.empty and self.mse < CONFIDENT_MSE


def _binarize(arr: np.ndarray) -> np.ndarray:
    gray = arr.mean(axis=2)
    return (gray > 0.45).astype(np.float32)


def normalize_strip(arr: np.ndarray) -> np.ndarray | None:
    """Binarize, crop to the bright-pixel bbox (name+cost text), resize.

    Returns None when the strip holds no glyphs (empty slot)."""
    mask = _binarize(arr)
    if int(mask.sum()) < EMPTY_BRIGHT_PX:
        return None
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    pad = 2
    r0, r1 = max(0, rows[0] - pad), min(mask.shape[0], rows[-1] + pad + 1)
    c0, c1 = max(0, cols[0] - pad), min(mask.shape[1], cols[-1] + pad + 1)
    img = Image.fromarray((mask[r0:r1, c0:c1] * 255).astype(np.uint8))
    return (
        np.asarray(img.resize((STRIP_W, STRIP_H)), dtype=np.float32) > 127
    ).astype(np.float32)


class IconLibrary:
    """mode 'card': templates are name-strip images (calibrated crops).
    mode 'icon': templates are cdragon square portraits (art fallback)."""

    def __init__(self, icon_dir: str | Path, mode: str = "icon") -> None:
        self.mode = mode
        self.templates: dict[str, np.ndarray] = {}
        for path in sorted(Path(icon_dir).glob("*.png")):
            arr = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
            if mode == "card":
                strip = normalize_strip(arr)
                if strip is not None:
                    self.templates[path.stem] = strip
            else:
                small = np.asarray(
                    Image.open(path).convert("RGB").resize((ICON_SIZE, ICON_SIZE)),
                    dtype=np.float32,
                ) / 255.0
                self.templates[path.stem] = small

    def match(self, crop: np.ndarray) -> Match:
        probe = normalize_strip(crop) if self.mode == "card" else crop
        if probe is None:
            return Match(None, 0.0, None, 0.0, empty=True)
        pool = (
            {n: t for n, t in self.templates.items() if not n.startswith("Empty")}
            if self.mode == "card"
            else self.templates
        )
        best, second = None, None
        best_mse, second_mse = float("inf"), float("inf")
        for name, ref in pool.items():
            mse = float(np.mean((probe - ref) ** 2))
            if mse < best_mse:
                second, second_mse = best, best_mse
                best, best_mse = name, mse
            elif mse < second_mse:
                second, second_mse = name, mse
        return Match(best, best_mse, second, second_mse)


def _crop_strip(
    img: Image.Image, box: tuple[float, float, float, float], mode: str
) -> np.ndarray:
    w, h = img.size
    l, t, r, b = box
    crop = img.crop((int(l * w), int(t * h), int(r * w), int(b * h))).convert("RGB")
    if mode == "icon":
        crop = crop.resize((ICON_SIZE, ICON_SIZE))
    return np.asarray(crop, dtype=np.float32) / 255.0


def detect_shop(img: Image.Image, lib: IconLibrary) -> list[Match]:
    """One Match per shop slot (5 slots, left to right)."""
    bar = is_shop_bar(img)
    columns = bar_card_columns(img) if bar else None
    return [
        lib.match(_crop_strip(img, strip_box(i, bar, columns), lib.mode))
        for i in range(5)
    ]


if __name__ == "__main__":
    import sys

    shot = Image.open(sys.argv[1])
    src = sys.argv[2] if len(sys.argv) > 2 else "data/card_templates/18"
    mode = "card" if "card_templates" in src else "icon"
    library = IconLibrary(src, mode=mode)
    for slot, m in enumerate(detect_shop(shot, library), 1):
        flag = "" if m.confident else "  [low confidence]"
        if m.empty:
            flag = "  [empty]"
        print(
            f"slot {slot}: {m.name} (mse={m.mse:.4f})"
            f"  runner-up {m.runner_up} ({m.runner_up_mse:.4f}){flag}"
        )
