from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = 1


class ActionType(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"
    ROLL = "roll"
    LEVEL = "level"
    PLAY_COMP = "play_comp"
    SLAM_ITEM = "slam_item"
    CHOOSE_AUGMENT = "choose_augment"


@dataclass(frozen=True)
class UnitState:
    name: str
    star_level: int = 1
    items: tuple[str, ...] = ()
    # (row, col) on the 4x7 TFT board; None when position is unknown/irrelevant.
    position: tuple[int, int] | None = None


@dataclass(frozen=True)
class ShopUnit:
    name: str
    cost: int


@dataclass(frozen=True)
class TraitState:
    """A trait currently contributing on board. `count` is the number of
    unique units carrying it; breakpoints live in the knowledge DB."""

    name: str
    count: int


@dataclass
class OpponentState:
    """Imperfect scouting record. `last_seen_stage` makes staleness explicit —
    consumers must never treat stale observations as current."""

    id: str
    hp: int | None = None
    level: int | None = None
    observed_units: list[UnitState] = field(default_factory=list)
    known_items: list[str] = field(default_factory=list)
    likely_comp: str | None = None
    contested_units: frozenset[str] = frozenset()
    last_seen_stage: str | None = None


@dataclass(frozen=True)
class CombatRecord:
    stage: str
    result: str  # "win" | "loss"
    damage_taken: int = 0
    opponent_id: str | None = None


@dataclass
class GameState:
    """Canonical observation passed to the decision engine. The engine must not
    care how this was produced (manual input, OCR, replay, another program).

    Fields beyond the required five are optional so partially observed states
    remain representable; `state_confidence` lets an observer say how much of
    the state is trustworthy.
    """

    patch: str
    stage: str
    hp: int
    gold: int
    level: int
    xp: int = 0
    board: list[UnitState] = field(default_factory=list)
    bench: list[UnitState] = field(default_factory=list)
    shop: list[ShopUnit] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    completed_items: list[str] = field(default_factory=list)
    augments: list[str] = field(default_factory=list)
    # Augments currently offered to pick from (empty = no pending choice).
    augment_choices: list[str] = field(default_factory=list)
    # Lobby summaries; may be supplied directly or derived from `opponents`.
    contested_comps: dict[str, int] = field(default_factory=dict)
    contested_units: dict[str, int] = field(default_factory=dict)

    schema_version: int = SCHEMA_VERSION
    set: str | None = None
    streak: int = 0  # positive = win streak, negative = loss streak
    consumables: list[str] = field(default_factory=list)
    traits: list[TraitState] = field(default_factory=list)
    opponents: list[OpponentState] = field(default_factory=list)
    history: list[CombatRecord] = field(default_factory=list)
    interest: int | None = None
    streak_income: int | None = None
    state_confidence: float = 1.0

    def contested_unit_count(self, unit: str) -> int:
        """Copies of `unit` believed held by opponents, from whichever
        observation source is populated."""
        total = self.contested_units.get(unit, 0)
        for opp in self.opponents:
            if unit in opp.contested_units or any(
                u.name == unit for u in opp.observed_units
            ):
                total += 1
        return total


@dataclass(frozen=True)
class CandidateAction:
    action_type: ActionType
    target: str | None = None
    target_gold: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreFeature:
    name: str
    value: float
    weight: float
    contribution: float
    reason: str


@dataclass
class ScoredAction:
    action: CandidateAction
    score: float
    baseline_score: float
    context_score: float
    confidence: float
    features: list[ScoreFeature] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    actions: list[ScoredAction]
    latency_ms: float
    candidate_count: int
