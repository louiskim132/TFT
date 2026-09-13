"""Need-based augment reasoning.

No accessible source publishes per-augment strength stats, so augment value is
derived instead of looked up: compare the observed state against guide
benchmarks (level pacing, expected gold, expected items per stage — the same
numbers overlay apps like Porofessor show), find the largest deficit, and
prefer the augment whose category covers it.

Benchmarks are documented heuristics, not scraped values; they live in code
because they encode game knowledge, not provider data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .models import GameState
from .stats import CompStats


class AugmentCategory(str, Enum):
    ECON = "econ"
    XP = "xp"
    ITEM = "item"
    TRAIT = "trait"
    COMBAT = "combat"


_KEYWORDS: list[tuple[tuple[str, ...], AugmentCategory]] = [
    (
        (
            "gold", "interest", "rich", "hedge fund", "jackpot", "income",
            "economy", "ticket", "shop", "reroll", "free", "escrow", "refund",
            "shopping", "trade",
        ),
        AugmentCategory.ECON,
    ),
    (
        (
            "level", "xp", "experience", "patient study", "march of progress",
            "level up", "wisdom", "elevation", "climb",
        ),
        AugmentCategory.XP,
    ),
    (
        (
            "item", "component", "anvil", "treasure", "pandora", "grab bag",
            "artifact", "buried", "forge", "armory", "loot", "supply",
        ),
        AugmentCategory.ITEM,
    ),
    (
        ("emblem", "crest", "crown", "heart", "soul", "tome", "trait"),
        AugmentCategory.TRAIT,
    ),
]


def classify_augment(name: str) -> AugmentCategory:
    """Category from the augment's display name. Unmatched names default to
    COMBAT — the modal category — rather than UNKNOWN so the deficit model can
    still rank them."""
    lowered = name.lower()
    for keywords, category in _KEYWORDS:
        if any(k in lowered for k in keywords):
            return category
    return AugmentCategory.COMBAT


# --- stage benchmarks -------------------------------------------------------
# Anchor curves: at a given stage, a "standard tempo" board should be at least
# this level / hold about this much gold / field about this many items
# (completed items + half-finished components). Values between anchors use the
# most recent anchor (step interpolation).

_LEVEL_CURVE: list[tuple[str, int]] = [
    ("1-1", 1), ("2-1", 4), ("2-5", 5), ("3-2", 6), ("3-6", 7),
    ("4-2", 7), ("4-5", 8), ("5-3", 9), ("6-2", 10),
]

_GOLD_CURVE: list[tuple[str, float]] = [
    ("1-1", 0), ("2-1", 10), ("2-5", 20), ("3-1", 30), ("3-5", 50),
    ("4-2", 50), ("4-5", 25), ("5-3", 30), ("6-1", 40),
]

_ITEM_CURVE: list[tuple[str, float]] = [
    ("1-1", 0), ("2-1", 1.5), ("3-1", 2.5), ("4-1", 3.5), ("5-1", 4.5),
    ("6-1", 5.5),
]

# XP needed to go from level n to n+1 (current set: 1 gold buys 1 XP).
_XP_COSTS = {1: 2, 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 56, 8: 80, 9: 100}

_STAGE_RE = re.compile(r"^(\d+)-(\d+)$")


def _stage_index(stage: str) -> float | None:
    m = _STAGE_RE.match(stage.strip())
    if not m:
        return None
    return int(m.group(1)) * 10 + int(m.group(2))


def _curve_value(curve: list[tuple[str, float | int]], stage: str) -> float:
    idx = _stage_index(stage)
    if idx is None:
        return 0.0
    value = curve[0][1]
    for anchor_stage, anchor_value in curve:
        if _stage_index(anchor_stage) <= idx:  # type: ignore[operator]
            value = anchor_value
        else:
            break
    return float(value)


@dataclass(frozen=True)
class NeedProfile:
    """How far the state sits behind benchmarks, in normalized units (~1.0 =
    one full benchmark step behind). Negative deltas clamp to 0 — being ahead
    removes the need, it does not create a new one."""

    xp: float  # levels behind, expressed via their gold-equivalent XP cost
    econ: float  # gold behind the stage's expected holdings
    items: float  # completed-item equivalents missing
    expected_level: int
    xp_deficit_gold: int  # raw gold cost to reach expected level
    gold_deficit: float
    item_deficit: float

    def by_category(self) -> dict[AugmentCategory, float]:
        return {
            AugmentCategory.XP: self.xp,
            AugmentCategory.ECON: self.econ,
            AugmentCategory.ITEM: self.items,
            # Combat is the default when nothing is lacking; trait augments
            # rank via the comp/board fit features, not a baseline pull.
            AugmentCategory.COMBAT: 0.15,
            AugmentCategory.TRAIT: 0.1,
        }

    def top_need(self) -> AugmentCategory:
        return max(self.by_category().items(), key=lambda kv: kv[1])[0]


def compute_needs(
    state: GameState, comps: list[CompStats] | None = None
) -> NeedProfile:
    expected_level = int(_curve_value(_LEVEL_CURVE, state.stage))

    # A chosen comp's plan overrides the generic curve: a Slow-Roll-5 board is
    # not "behind" for sitting at 5 in stage 3. Best comp = largest roster
    # overlap with units already owned.
    if comps:
        owned = {u.name for u in state.board + state.bench}
        best = max(
            (c for c in comps if c.core_units & owned),
            key=lambda c: len(c.core_units & owned),
            default=None,
        )
        if (
            best is not None
            and best.typical_level is not None
            and best.typical_level <= 7
            and (_stage_index(state.stage) or 99) < _stage_index("4-1")
        ):
            expected_level = min(expected_level, best.typical_level)

    # Gold cost of the missing levels, minus XP already banked.
    xp_needed = sum(
        _XP_COSTS.get(lvl, 100) for lvl in range(state.level, expected_level)
    )
    xp_deficit_gold = max(0, xp_needed - state.xp)

    gold_deficit = max(
        0.0, _curve_value(_GOLD_CURVE, state.stage) - state.gold
    )
    current_items = len(state.completed_items) + 0.5 * len(state.components)
    item_deficit = max(
        0.0, _curve_value(_ITEM_CURVE, state.stage) - current_items
    )

    return NeedProfile(
        xp=min(1.5, xp_deficit_gold / 40.0),
        econ=min(1.5, gold_deficit / 30.0),
        items=min(1.5, item_deficit / 2.0),
        expected_level=expected_level,
        xp_deficit_gold=xp_deficit_gold,
        gold_deficit=gold_deficit,
        item_deficit=item_deficit,
    )
