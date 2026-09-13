from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionType(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    ROLL = "roll"
    LEVEL = "level"
    PLAY_COMP = "play_comp"
    SLAM_ITEM = "slam_item"


@dataclass(frozen=True)
class UnitState:
    name: str
    star_level: int = 1
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShopUnit:
    name: str
    cost: int


@dataclass
class GameState:
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
    contested_comps: dict[str, int] = field(default_factory=dict)
    contested_units: dict[str, int] = field(default_factory=dict)


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
