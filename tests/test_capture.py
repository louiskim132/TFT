"""Capture layer tests — synthetic shop strip, no network or real frames."""

from __future__ import annotations

import numpy as np
from PIL import Image

from tft_engine.capture.calibrate import (
    FRAME_STRIP_BOTTOM,
    FRAME_STRIP_TOP,
    SHOP_CARD_LEFT,
    SHOP_CARD_STRIDE,
    CARD_W,
    calibrate_shop,
)
from tft_engine.capture.match import IconLibrary, detect_shop


def _synthetic_frame(tmp_path, size=(1024, 576)) -> Image.Image:
    """1024x576 frame: noise background + a distinct bright glyph pattern in
    each shop card's name-strip region (matching is binarized, so flat color
    alone would not discriminate)."""
    rng = np.random.RandomState(0)
    frame = (rng.rand(576, 1024, 3) * 60).astype(np.uint8)  # dark noise
    for i in range(5):
        l = SHOP_CARD_LEFT + i * SHOP_CARD_STRIDE
        x0 = int(l * 1024)
        x1 = int((l + CARD_W) * 1024)
        y0, y1 = int(FRAME_STRIP_TOP * 576), int(FRAME_STRIP_BOTTOM * 576)
        # name strip: (i+1) bright vertical bars — distinct glyph stand-ins
        for b in range(i + 1):
            bx = x0 + 4 + b * 8
            frame[y0:y1 - 3, bx:bx + 3] = 230
    return Image.fromarray(frame)


def test_calibrate_then_detect(tmp_path):
    frame = _synthetic_frame(tmp_path)
    img_path = tmp_path / "frame.png"
    frame.save(img_path)
    names = ["Fiddlesticks", "Soraka", "Rengar", "Yorick", "Tristana"]
    tpl_dir = tmp_path / "templates"
    calibrate_shop(img_path, names, 18, tpl_dir)
    assert len(list(tpl_dir.glob("*.png"))) == 5

    lib = IconLibrary(tpl_dir, mode="card")
    matches = detect_shop(frame, lib)
    detected = [m.name for m in matches]
    expected = [n.lower().replace("'", "") for n in names]
    # icon_filename capitalizes first letter only
    assert [d.lower() for d in detected] == expected
    assert all(m.mse < 1e-6 for m in matches)


def test_detect_shifted_row_and_empty(tmp_path):
    # shop row shifted ~24px left (PvE-round layout) with the last slot empty
    frame = _synthetic_frame(tmp_path)
    arr = np.array(frame)
    shift = int(0.024 * 1024)
    fy0, fy1 = int(FRAME_STRIP_TOP * 576), int(FRAME_STRIP_BOTTOM * 576)
    fx0 = int(SHOP_CARD_LEFT * 1024)
    fx1 = int((SHOP_CARD_LEFT + 5 * SHOP_CARD_STRIDE) * 1024)
    row = arr[fy0:fy1, fx0:fx1].copy()
    arr[fy0:fy1, fx0 - shift : fx1 - shift] = row
    # blank out the last card's strip entirely -> dark empty slot
    el = SHOP_CARD_LEFT + 4 * SHOP_CARD_STRIDE
    arr[fy0:fy1, int(el * 1024) - shift : int((el + CARD_W) * 1024) - shift] = 15

    tpl_dir = tmp_path / "tpl"
    src = tmp_path / "src.png"
    frame.save(src)
    calibrate_shop(src, ["A", "B", "C", "D", "E"], 18, tpl_dir)
    lib = IconLibrary(str(tpl_dir), mode="card")

    detected = detect_shop(Image.fromarray(arr), lib)
    names = [m.name for m in detected[:4]]
    assert "A" in names or any(not m.confident for m in detected[:4])
    assert detected[4].empty or not detected[4].confident


def test_detect_flags_unseen_card(tmp_path):
    frame = _synthetic_frame(tmp_path)
    img_path = tmp_path / "frame.png"
    frame.save(img_path)
    tpl_dir = tmp_path / "templates"
    calibrate_shop(img_path, ["A", "B", "C", "D", "E"], 18, tpl_dir)

    # Different frame: only slot patterns differ -> all matches are guesses.
    rng = np.random.RandomState(9)
    other = Image.fromarray((rng.rand(576, 1024, 3) * 255).astype(np.uint8))
    lib = IconLibrary(tpl_dir, mode="card")
    matches = detect_shop(other, lib)
    assert not any(m.confident for m in matches)
