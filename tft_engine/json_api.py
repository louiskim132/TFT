from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .engine import DecisionEngine
from .models import GameState
from .state_io import game_state_from_dict, game_state_to_dict  # noqa: F401 (re-export)


def decision_to_dict(engine: DecisionEngine, payload: Mapping[str, Any]) -> dict[str, Any]:
    result = engine.decide(game_state_from_dict(payload))
    return {
        "latency_ms": result.latency_ms,
        "candidate_count": result.candidate_count,
        "actions": [asdict(action) for action in result.actions],
    }
