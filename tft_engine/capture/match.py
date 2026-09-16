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
# Name-strip MSE: JPEG noise puts same-card cross-frame error around 0.01;
# different champions land >0.025. Between is a "probable" grey zone.
CONFIDENT_MSE = 0.015
# Bottom fraction of the card interior holding name+cost — glyph shapes are
# the most discriminative region and survive compression best.
NAME_STRIP_TOP = 0.72
# Empty slots render a flat dark card; variance stays near zero.
EMPTY_VAR = 0.004


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
        """`crop` is an ICON_SIZE² probe resized from the card box. Card mode
        compares binarized name strips against *named* templates only —
        Empty* handling lives in detect_shop so jittered flat regions can't
        win the argmin."""
        if self.mode == "card":
            cut = int(ICON_SIZE * NAME_STRIP_TOP)
            probe = (crop[cut:].mean(axis=2) > 0.35).astype(np.float32)
            pool = {
                n: (t[cut:].mean(axis=2) > 0.35).astype(np.float32)
                for n, t in self.templates.items()
                if not n.startswith("Empty")
            }
        else:
            probe, pool = crop, self.templates
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

    def is_empty(self, crop: np.ndarray) -> bool:
        """Flat render, or a saved Empty* card-back template matches."""
        if float(crop.var()) < EMPTY_VAR:
            return True
        cut = int(ICON_SIZE * NAME_STRIP_TOP)
        probe = (crop[cut:].mean(axis=2) > 0.35).astype(np.float32)
        for n, t in self.templates.items():
            if not n.startswith("Empty"):
                continue
            ref = (t[cut:].mean(axis=2) > 0.35).astype(np.float32)
            if float(np.mean((probe - ref) ** 2)) < CONFIDENT_MSE:
                return True
        return False


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
    """One Match per shop slot (5 slots, left to right). Shop row position
    shifts a few px between phases/resolutions — card mode searches a small
    (dx, dy) neighborhood and keeps the best-scoring offset."""
    left0, top, cw, ch = lib.slot_box
    out: list[Match] = []
    for i in range(5):
        left = left0 + i * SHOP_CARD_STRIDE
        if lib.mode == "card":
            best: Match | None = None
            for dy in range(-4, 5):
                t = top + dy / img.size[1]
                for dx in range(-28, 29, 4):  # includes 0
                    l = left + dx / img.size[0]
                    m = lib.match(
                        _crop_fraction(img, (l, t, l + cw, t + ch))
                    )
                    if best is None or m.mse < best.mse:
                        best = m
            # Empty is a separate decision at the canonical box — jittered
            # flat regions would otherwise outscore real matches.
            canonical = _crop_fraction(img, (left, top, left + cw, top + ch))
            if best is not None and not best.confident and lib.is_empty(canonical):
                best = Match(None, 0.0, best.name, best.mse, empty=True)
            out.append(best)
        else:
            out.append(
                lib.match(_crop_fraction(img, (left, top, left + cw, top + ch)))
            )
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
