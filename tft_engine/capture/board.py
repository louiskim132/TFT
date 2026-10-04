"""Board and side-panel perception for full-game frames.

Reference geometry was measured at 1024x575; all regions are fractions of
the image so they scale. At this resolution live board units render ~60-80px
tall and animate — direct 3D-model matching is a weak signal. The reliable
primitives, in order of strength:

- damage-stats panel  -> roster portraits + star pips + damage, both boards
- scout cards         -> opponent unit name text + star pips
- green health bars   -> occupied-unit anchors on the board
- on-model glow       -> 2-star white aura / 3-star gold aura (fallback)

The stats panel portraits are deterministic per-unit renders; matching
against art assets (cdragon icons) is approximate, so panel templates
should be calibrated from labeled panel screenshots like shop strips were.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- health bars
# Own-unit health bars are a saturated green, ~1-3px tall and 20-40px wide at
# 1024x575. Enemy bars are red; neutrals yellow — the mask below is own-green.
_BAR_MIN_W_FRAC = 0.015   # 15px at 1024
_BAR_MAX_W_FRAC = 0.05    # 51px
_BAR_MAX_H = 4
_GREEN_LO = (0.05, 0.45, 0.10)


def _green_mask(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (g > _GREEN_LO[1]) & (g > r * 1.6) & (g > b * 1.4) & (g - r > 0.20)


@dataclass(frozen=True)
class BarAnchor:
    """A detected health bar: (cx, cy) is the unit anchor in pixels."""

    cx: float
    cy: float
    width: int

    @property
    def fx(self) -> float:
        return self.cx

    @property
    def fy(self) -> float:
        return self.cy


def find_health_bars(img: Image.Image) -> list[BarAnchor]:
    """Detect own-unit health bars; anchor = bar center, in pixels."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    mask = _green_mask(rgb)
    min_w, max_w = int(_BAR_MIN_W_FRAC * w), int(_BAR_MAX_W_FRAC * w)
    # horizontal runs of green, per row
    runs: list[tuple[int, int, int]] = []  # (y, x0, x1)
    for y in range(h):
        row = mask[y]
        xs = np.where(row)[0]
        if len(xs) == 0:
            continue
        # split into contiguous runs
        cuts = np.where(np.diff(xs) > 2)[0]
        for seg in np.split(xs, cuts + 1):
            if min_w <= len(seg) <= max_w:
                runs.append((y, int(seg[0]), int(seg[-1])))
    # merge runs on adjacent rows with overlapping x (a bar is 1-3px tall)
    bars: list[BarAnchor] = []
    used = [False] * len(runs)
    for i, (y, x0, x1) in enumerate(runs):
        if used[i]:
            continue
        used[i] = True
        lo, hi, yy = x0, x1, y
        for j in range(i + 1, len(runs)):
            y2, a0, a1 = runs[j]
            if used[j] or y2 - yy > _BAR_MAX_H:
                continue
            if a0 <= hi + 3 and a1 >= lo - 3:
                used[j] = True
                lo, hi, yy = min(lo, a0), max(hi, a1), y2
        if min_w <= hi - lo <= max_w:
            bars.append(BarAnchor((lo + hi) / 2, float(y), hi - lo))
    return bars


# ---------------------------------------------------------------- stat panel
# The damage-stats overlay is a dark panel on the right half of the frame.
# Two columns: own board (left) and current opponent (right). Each row is
# portrait + damage number + bar. Star pips (pale blue-white ~3px stars)
# sit on the portrait's bottom edge.
PANEL_LEFT = 0.72
# measured at 1024x575: own portraits x ~0.81-0.84, opponent ~0.91-0.94;
# kept tight so damage digits to the right don't enter the band
PANEL_COLS = {"own": (0.808, 0.844), "opp": (0.905, 0.945)}
PANEL_TOP = 0.20
PANEL_BOTTOM = 0.80
_PORTRAIT_MIN_SIDE = 14
_PORTRAIT_MAX_SIDE = 40
_PANEL_BG = 0.13


def stat_panel_open(img: Image.Image) -> bool:
    """The stats overlay is a flat dark rounded panel; when absent, the same
    screen region shows game content. Probe the column between the two
    rosters — nearly all dark when the panel is open."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = a.shape[:2]
    z = a[int(0.25 * h) : int(0.75 * h), int(0.860 * w) : int(0.895 * w)]
    return float((z.mean(axis=2) < 0.18).mean()) > 0.6


def _colorfulness(col: np.ndarray) -> np.ndarray:
    """Per-row 'is a portrait here' score: portraits are saturated squares
    inside a flat dark panel."""
    s = col.std(axis=2) + (col.max(axis=2) - col.min(axis=2))
    return s.mean(axis=1)


def stat_panel_portraits(
    img: Image.Image, column: str = "own"
) -> list[tuple[int, int, int, int, Image.Image]]:
    """Detect portrait boxes in one panel column.

    Content rows score >0.10, inter-portrait gaps ~0.07. Header/name rows
    also score high, so a segment only counts as a portrait when it is
    roughly square (portraits ~17-30px on a side at 1024x575).
    Returns (y0, y1, x0, x1, crop) per detected portrait, top to bottom —
    the crop is extended a few px below the box so star pips that hang off
    the portrait's bottom edge stay inside."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    x0, x1 = PANEL_COLS[column]
    col = rgb[int(PANEL_TOP * h) : int(PANEL_BOTTOM * h), int(x0 * w) : int(x1 * w)]
    score = _colorfulness(col)
    on = score > 0.10
    # merge content runs split by <=3px dips (portrait interiors have
    # occasional dark rows), then keep square-ish segments
    out: list[tuple[int, int, int, int, Image.Image]] = []
    y = 0
    top = int(PANEL_TOP * h)
    while y < len(on):
        if not on[y]:
            y += 1
            continue
        y1 = y
        while y1 + 1 < len(on):
            gap = 0
            while y1 + 1 + gap < len(on) and not on[y1 + 1 + gap]:
                gap += 1
            if gap <= 3 and y1 + 1 + gap < len(on) and on[y1 + 1 + gap]:
                y1 += 1 + gap
            else:
                break
        side = y1 - y + 1
        if _PORTRAIT_MIN_SIDE <= side <= _PORTRAIT_MAX_SIDE:
            # roster rows are evenly spaced; a >45px gap means the roster
            # ended and below this is other UI (scoreboard etc.)
            if out and top + y - out[-1][1] > 45:
                break
            cx0, cx1 = int(x0 * w), int(x1 * w)
            crop = img.crop((cx0, top + y, cx1, min(h, top + y1 + 1 + 6)))
            out.append((top + y, top + y1 + 1, cx0, cx1, crop))
        y = y1 + 1
    return out


def count_star_pips(portrait: Image.Image, box_h: int | None = None) -> int:
    """Star pips are pale blue-white ~3px stars on the portrait's bottom edge.

    Signature measured at 1024x575: channels ~(0.5,0.6,0.7), blue-leaning.
    The crop may extend a few px below the portrait box — `box_h` is the
    true portrait height so the pip band can be located at its bottom edge.
    Returns 0, 2 or 3 (a 1-star unit has no pips)."""
    a = np.asarray(portrait.convert("RGB"), dtype=np.float32) / 255
    h, w, _ = a.shape
    ph = box_h if box_h is not None else h
    # pips sit on the portrait's bottom edge: the last ~4 rows plus a sliver
    # below. Wider bands pick up bright portrait content and merge runs.
    y0 = max(0, ph - 4)
    z = a[y0 : min(h, ph + 3), int(w * 0.15) : int(w * 0.85)]
    r, b = z[..., 0], z[..., 2]
    # pale blue-white: bright, blue-leaning or neutral
    mask = (z.sum(axis=2) > 1.35) & (b > r * 0.95)
    cols = mask.sum(axis=0) > 0
    # each pip is ~3px wide. Runs >8px are portrait content; 1px runs count
    # only when strongly blue (b>>r) — a pip clipped by the box edge, not a
    # warm frame-corner glint.
    strong = mask & (b > r * 1.15)
    cols_strong = strong.sum(axis=0) > 0
    pips, run = 0, 0
    for i, v in enumerate(list(cols) + [False]):
        if v:
            run += 1
        elif run:
            if 2 <= run <= 8 or (run == 1 and cols_strong[i - 1]):
                pips += 1
            run = 0
    return min(pips, 3)


# ---------------------------------------------------------------- trait panel
# The left HUD strip lists active traits: hex icon, count badge, name, and
# threshold progress (e.g. "2 > 4 > 6"). Rows are evenly spaced from ~y0.22.
# Icon tone signals state: colored = active tier, gray = below threshold.
# Lux-variant traits (개화/햇빛/검은 가시/원시/…) appear here — the variant
# evidence source noted in the board-template manifest.
TRAIT_ROW_TOP = 0.222
TRAIT_ROW_STRIDE = 0.0455
TRAIT_MAX_ROWS = 12
TRAIT_ICON = (0.034, 0.049)  # hex icon (saturated)
TRAIT_COUNT = (0.049, 0.058)  # dark badge with white count digit
TRAIT_NAME = (0.059, 0.150)  # white name text (thresholds on the row below)


@dataclass(frozen=True)
class TraitRow:
    y: int
    icon: Image.Image
    name: Image.Image
    active: bool  # icon is colored/bright rather than dark gray


def trait_rows(img: Image.Image) -> list[TraitRow]:
    """Extract each visible trait row: icon + name crops, active flag.

    A row exists when its name band holds white glyph pixels (the panel
    shows only relevant traits — trailing rows are absent)."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    out: list[TraitRow] = []
    for k in range(TRAIT_MAX_ROWS):
        y = int((TRAIT_ROW_TOP + k * TRAIT_ROW_STRIDE) * h)
        rh = int(0.040 * h)
        nx0, nx1 = int(TRAIT_NAME[0] * w), int(TRAIT_NAME[1] * w)
        band = rgb[y : y + rh, nx0:nx1]
        # white name glyphs: high min-channel (inactive rows render dimmer)
        if int((band.min(axis=2) > 0.35).sum()) < 8:
            break
        ix0, ix1 = int(TRAIT_ICON[0] * w), int(TRAIT_ICON[1] * w)
        icon = img.crop((ix0, y, ix1, y + rh)).convert("RGB")
        arr = np.asarray(icon, dtype=np.float32) / 255
        # rows past the list ("1+ more" footer, other UI) have no icon
        if float(arr.std()) < 0.03:
            break
        name = img.crop((nx0, y, nx1, y + rh))
        # active tiers render colored icons (sat ~0.08-0.20); below-threshold
        # rows go grayscale (sat ~0.01-0.02). Caveat: blue-tinted inactive
        # icons (e.g. 개화) sit mid-range — the unit count is the stronger
        # signal for roster inference anyway.
        sat = float((arr.max(axis=2) - arr.min(axis=2)).mean())
        active = sat > 0.05
        out.append(TraitRow(y, icon, name, active))
    return out


# ---------------------------------------------------------------- bench strip
# Left edge: a column of ~9 bench slots (square portraits); the top slot in
# this frame held a 5-cost unit with a gold cost badge. Empty slots are
# flat dark squares.
BENCH_X = (0.005, 0.024)
BENCH_TOP = 0.213
BENCH_STRIDE = 0.057
BENCH_SLOTS = 9


def bench_portraits(img: Image.Image) -> list[Image.Image | None]:
    """One entry per bench slot; None for empty (flat dark) slots."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    x0, x1 = int(BENCH_X[0] * w), int(BENCH_X[1] * w)
    out: list[Image.Image | None] = []
    for k in range(BENCH_SLOTS):
        y = int((BENCH_TOP + k * BENCH_STRIDE) * h)
        side = int(0.042 * h)
        z = rgb[y : y + side, x0:x1]
        # empty slots are flat dark squares (std ~0.07); occupied ~0.19+
        if float(z.std()) < 0.12:
            out.append(None)
            continue
        out.append(img.crop((x0, y, x0 + side, y + side)).convert("RGB"))
    return out


# ---------------------------------------------------------------- scout cards
# When scouting (clicking a scoreboard entry), a card per deployed enemy unit
# shows its name text and star pips — the strongest opponent-read source.
# Regions measured at 1024x575; name text is matchable with the shop-strip
# template technique.
SCOUT_CARD_TOP = 0.30
SCOUT_CARD_BOTTOM = 0.95


# ---------------------------------------------------------------- glow (stars)
def star_aura(img: Image.Image, anchor: BarAnchor) -> int:
    """On-board star heuristic: 2-star units carry a white glow, 3-star gold.

    Returns 1/2/3 — 1 when neither aura is found. Weak signal; the stats
    panel pips are preferred when available."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    h, w = rgb.shape[:2]
    cx, cy = int(anchor.cx), int(anchor.cy)
    y0, y1 = max(0, cy), min(h, cy + int(0.10 * h))
    x0, x1 = max(0, cx - int(0.04 * w)), min(w, cx + int(0.04 * w))
    z = rgb[y0:y1, x0:x1]
    r, g, b = z[..., 0], z[..., 1], z[..., 2]
    white = ((r > 0.75) & (g > 0.75) & (b > 0.75)).sum()
    gold = ((r > 0.65) & (g > 0.50) & (b < 0.25) & (r > b * 2.5)).sum()
    n = z.shape[0] * z.shape[1]
    if gold > 0.02 * n:
        return 3
    if white > 0.03 * n:
        return 2
    return 1


def unit_crop(img: Image.Image, anchor: BarAnchor) -> Image.Image:
    """Crop the unit model below its health bar (excludes bar + item row).

    Item icons sit in a row directly under the bar; the model occupies the
    region from just under the bar to ~75px below at 1024x575."""
    w, h = img.size
    cx, cy = int(anchor.cx), int(anchor.cy)
    half = int(0.038 * w)
    x0, x1 = max(0, cx - half), min(w, cx + half)
    y0, y1 = cy + int(0.008 * h), min(h, cy + int(0.135 * h))
    return img.crop((x0, y0, x1, y1))


@dataclass
class BoardScan:
    anchors: list[BarAnchor] = field(default_factory=list)
    own_portraits: list[tuple[int, int, int, int, Image.Image]] = field(
        default_factory=list
    )
    opp_portraits: list[tuple[int, int, int, int, Image.Image]] = field(
        default_factory=list
    )
    stats_panel: bool = False

    @property
    def occupied(self) -> int:
        return len(self.anchors)


def scan_frame(img: Image.Image) -> BoardScan:
    """One-pass extraction of the frame's board primitives."""
    panel = stat_panel_open(img)
    return BoardScan(
        anchors=find_health_bars(img),
        own_portraits=stat_panel_portraits(img, "own") if panel else [],
        opp_portraits=stat_panel_portraits(img, "opp") if panel else [],
        stats_panel=panel,
    )
