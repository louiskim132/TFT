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

from .calibrate import bar_name_boxes, is_shop_bar, strip_box

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


def _blur2(m: np.ndarray) -> np.ndarray:
    """3x3-then-3x3 box blur (≈5x5): softens glyph edges for matching."""
    out = np.zeros_like(m)
    for _ in range(2):
        acc = np.zeros_like(m)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                acc += np.roll(np.roll(m, dy, 0), dx, 1)
        out = acc / 9.0
        m = out
    return out


def normalize_strip(arr: np.ndarray) -> np.ndarray | None:
    """Binarize, crop to the bottom-most text row run (name + cost), resize.

    The name row is the lowest contiguous band of rows containing real glyph
    mass — stray bright pixels above/below it (trait bleed, edge sparkle)
    are ignored. Returns None when the strip holds no glyphs (empty slot).
    Polarity is canonicalized so glyphs are always bright: bright banners
    (gold 5-costs) would otherwise invert to dark-text-on-white."""
    mask = _binarize(arr)
    if float(mask.mean()) > 0.5:
        mask = 1.0 - mask
    if int(mask.sum()) < EMPTY_BRIGHT_PX:
        return None
    row_counts = mask.sum(axis=1)
    text_row = row_counts > max(2.0, 0.02 * mask.shape[1])
    runs: list[tuple[int, int]] = []
    i = 0
    while i < mask.shape[0]:
        if text_row[i]:
            j = i
            while j + 1 < mask.shape[0] and text_row[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    if not runs:
        return None
    # the name row is the bottom-most *substantial* run (ignores a thin
    # bright line at the bar's bottom edge)
    masses = [int(mask[r[0] : r[1] + 1].sum()) for r in runs]
    peak = max(masses)
    substantial = [r for r, m in zip(runs, masses) if m >= 0.3 * peak]
    r0, r1 = substantial[-1]
    sub = mask[r0 : r1 + 1]
    cols = np.where(sub.any(axis=0))[0]
    pad = 2
    c0 = max(0, cols[0] - pad)
    c1 = min(mask.shape[1], cols[-1] + pad + 1)
    r0p = max(0, r0 - pad)
    r1p = min(mask.shape[0], r1 + pad + 1)
    img = Image.fromarray((mask[r0p:r1p, c0:c1] * 255).astype(np.uint8))
    return (
        np.asarray(img.resize((STRIP_W, STRIP_H)), dtype=np.float32) > 127
    ).astype(np.float32)


class IconLibrary:
    """mode 'card': templates are name-strip images (calibrated crops).
    mode 'icon': templates are cdragon square portraits (art fallback)."""

    def __init__(self, icon_dir: str | Path, mode: str = "icon") -> None:
        self.mode = mode
        # base unit name -> list of normalized variants (Name.png, Name__2.png)
        self.templates: dict[str, list[np.ndarray]] = {}
        for path in sorted(Path(icon_dir).glob("*.png")):
            stem = path.stem
            base = stem.split("__", 1)[0]
            arr = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
            if mode == "card":
                strip = normalize_strip(arr)
                if strip is not None:
                    self.templates.setdefault(base, []).append(_blur2(strip))
            else:
                small = np.asarray(
                    Image.open(path).convert("RGB").resize((ICON_SIZE, ICON_SIZE)),
                    dtype=np.float32,
                ) / 255.0
                self.templates.setdefault(base, []).append(small)

    def match(self, crop: np.ndarray) -> Match:
        probe = normalize_strip(crop) if self.mode == "card" else crop
        if probe is None:
            return Match(None, 0.0, None, 0.0, empty=True)
        bp = _blur2(probe) if self.mode == "card" else probe
        best, second = None, None
        best_mse, second_mse = float("inf"), float("inf")
        for name, variants in self.templates.items():
            if self.mode == "card" and name.startswith("Empty"):
                continue
            mse = min(self._score(bp, ref) for ref in variants)
            if mse < best_mse:
                second, second_mse = best, best_mse
                best, best_mse = name, mse
            elif mse < second_mse:
                second, second_mse = name, mse
        return Match(best, best_mse, second, second_mse)

    def _score(self, bp: np.ndarray, br: np.ndarray) -> float:
        if self.mode != "card":
            return float(np.mean((bp - br) ** 2))
        # blurred min-over-shifts MSE: forgiving of ±few-px glyph drift and
        # bbox aspect wobble, still separates distinct names.
        return min(
            float(np.mean((bp - np.roll(br, dx, 1)) ** 2)) for dx in range(-6, 7)
        )


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
    name_boxes = bar_name_boxes(img) if bar else None
    out: list[Match] = []
    for i in range(5):
        box = strip_box(i, bar, name_boxes)
        if box is None:
            out.append(Match(None, 0.0, None, 0.0, empty=True))
            continue
        out.append(lib.match(_crop_strip(img, box, lib.mode)))
    return out


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
