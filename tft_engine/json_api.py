from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .engine import DecisionEngine
from .models import GameState, ShopUnit, UnitState


def game_state_from_dict(payload: dict[str, Any]) -> GameState:
    return GameState(
        patch=str(payload["patch"]),
        stage=str(payload["stage"]),
        hp=int(payload["hp"]),
        gold=int(payload["gold"]),
        level=int(payload["level"]),
        xp=int(payload.get("xp", 0)),
        board=[
            UnitState(
                name=str(unit["name"]),
                star_level=int(unit.get("star_level", 1)),
                items=tuple(unit.get("items", [])),
            )
            for unit in payload.get("board", [])
        ],
        bench=[
            UnitState(
                name=str(unit["name"]),
                star_level=int(unit.get("star_level", 1)),
                items=tuple(unit.get("items", [])),
            )
            for unit in payload.get("bench", [])
        ],
        shop=[
            ShopUnit(name=str(unit["name"]), cost=int(unit["cost"]))
            for unit in payload.get("shop", [])
        ],
        components=[str(item) for item in payload.get("components", [])],
        completed_items=[str(item) for item in payload.get("completed_items", [])],
        augments=[str(item) for item in payload.get("augments", [])],
        contested_comps={str(k): int(v) for k, v in payload.get("contested_comps", {}).items()},
        contested_units={str(k): int(v) for k, v in payload.get("contested_units", {}).items()},
    )


def decision_to_dict(engine: DecisionEngine, payload: dict[str, Any]) -> dict[str, Any]:
    result = engine.decide(game_state_from_dict(payload))
    return {
        "latency_ms": result.latency_ms,
        "candidate_count": result.candidate_count,
        "actions": [asdict(action) for action in result.actions],
    }
