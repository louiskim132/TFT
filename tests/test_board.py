"""Board-perception tests — synthetic frames, no real screenshots."""

from __future__ import annotations

import numpy as np
from PIL import Image

from tft_engine.capture.board import (
    BarAnchor,
    count_star_pips,
    find_health_bars,
    scan_frame,
    star_aura,
    stat_panel_open,
    stat_panel_portraits,
)


def _frame(w=1024, h=575, seed=0) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return (rng.rand(h, w, 3) * 90).astype(np.uint8)  # dark game-ish noise


def _draw_bar(arr: np.ndarray, cx: int, cy: int, width: int, rows: int = 2) -> None:
    x0 = cx - width // 2
    arr[cy : cy + rows, x0 : x0 + width] = (30, 200, 60)


def test_health_bars_found_and_junk_rejected():
    arr = _frame()
    _draw_bar(arr, 355, 184, 32)
    _draw_bar(arr, 606, 185, 34)
    _draw_bar(arr, 300, 296, 30)
    # junk: a 3px green speck and an 80px green streak — both out of range
    arr[100:102, 50:53] = (30, 200, 60)
    arr[110:112, 60:140] = (30, 200, 60)
    bars = find_health_bars(Image.fromarray(arr))
    cxs = sorted(round(b.cx) for b in bars)
    assert len(cxs) == 3
    for got, want in zip(cxs, [300, 355, 606]):
        assert abs(got - want) <= 1
    assert all(184 <= b.cy <= 297 for b in bars)


def test_health_bars_merge_two_rows():
    arr = _frame()
    # one bar painted as two slightly offset 1px rows
    arr[200:201, 300:334] = (30, 200, 60)
    arr[201:202, 302:336] = (30, 200, 60)
    bars = find_health_bars(Image.fromarray(arr))
    assert len(bars) == 1
    assert abs(bars[0].cx - 318) <= 1


def _panel_frame() -> np.ndarray:
    """Dark stats panel on the right strip with two columns of portraits."""
    arr = _frame()
    arr[:, int(0.72 * 1024) :] = (20, 28, 34)  # flat dark panel
    # own column: 3 portraits at ~26px stride starting y=180
    rng = np.random.RandomState(1)
    for k in range(3):
        y = 180 + k * 52
        x0 = int(0.812 * 1024)
        arr[y : y + 20, x0 : x0 + 22] = rng.rand(20, 22, 3) * 255
    # opponent column: 2 portraits
    for k in range(2):
        y = 180 + k * 52
        x0 = int(0.910 * 1024)
        arr[y : y + 20, x0 : x0 + 22] = rng.rand(20, 22, 3) * 255
    return arr


def test_panel_gate_and_portraits():
    img = Image.fromarray(_panel_frame())
    assert stat_panel_open(img)
    own = stat_panel_portraits(img, "own")
    opp = stat_panel_portraits(img, "opp")
    assert len(own) == 3
    assert len(opp) == 2
    assert [y0 for y0, *_ in own] == [180, 232, 284]

    # no panel -> gate closes, scan_frame returns no portraits
    assert not stat_panel_open(Image.fromarray(_frame(seed=3)))


def test_portrait_far_straggler_excluded():
    arr = _panel_frame()
    rng = np.random.RandomState(2)
    x0 = int(0.812 * 1024)
    arr[180 + 3 * 52 + 80 : 180 + 3 * 52 + 100, x0 : x0 + 22] = (
        rng.rand(20, 22, 3) * 255
    )  # >45px below last portrait
    img = Image.fromarray(arr)
    own = stat_panel_portraits(img, "own")
    assert len(own) == 3


def test_star_pips():
    a = np.zeros((24, 24, 3), dtype=np.uint8) + 40
    img2 = Image.fromarray(a)
    assert count_star_pips(img2) == 0
    # two ~3px pale-blue stars on the bottom edge
    a[20:23, 7:10] = (110, 140, 170)
    a[20:23, 12:15] = (110, 140, 170)
    assert count_star_pips(Image.fromarray(a), box_h=24) == 2
    a[20:23, 17:20] = (110, 140, 170)
    assert count_star_pips(Image.fromarray(a), box_h=24) == 3


def test_star_aura():
    arr = _frame()
    _draw_bar(arr, 512, 300, 30)
    anchor = BarAnchor(512.0, 300.0, 30)
    img = Image.fromarray(arr)
    assert star_aura(img, anchor) == 1
    # white glow around the model zone
    arr[300:340, 480:545] = (220, 225, 230)
    assert star_aura(Image.fromarray(arr), anchor) == 2
    # gold aura wins over white
    arr[300:340, 480:545] = (200, 150, 40)
    assert star_aura(Image.fromarray(arr), anchor) == 3


def test_scan_frame_composes():
    arr = _panel_frame()
    _draw_bar(arr, 355, 184, 32)
    s = scan_frame(Image.fromarray(arr))
    assert s.stats_panel
    assert s.occupied == 1
    assert len(s.own_portraits) == 3
    assert len(s.opp_portraits) == 2
