"""Capture layer tests — synthetic shop strip, no network or real frames."""

from __future__ import annotations

import numpy as np
from PIL import Image

from tft_engine.capture.calibrate import calibrate_shop
from tft_engine.capture.match import (
    CARD_BOTTOM,
    CARD_TOP,
    CARD_W,
    SHOP_CARD_LEFT,
    SHOP_CARD_STRIDE,
    IconLibrary,
    detect_shop,
)


def _synthetic_frame(tmp_path, size=(1024, 576)) -> Image.Image:
    """1024x576 frame: noise background + a distinct color patch where each
    shop card's interior would render."""
    rng = np.random.RandomState(0)
    frame = (rng.rand(576, 1024, 3) * 60).astype(np.uint8)  # dark noise
    colors = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30), (200, 30, 200)]
    for i, color in enumerate(colors):
        l = SHOP_CARD_LEFT + i * SHOP_CARD_STRIDE
        x0, y0 = int(l * 1024), int(CARD_TOP * 576)
        x1, y1 = int((l + CARD_W) * 1024), int(CARD_BOTTOM * 576)
        frame[y0:y1, x0:x1] = color
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
