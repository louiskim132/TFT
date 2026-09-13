from __future__ import annotations

from .models import ActionType, CandidateAction, GameState
from .stats import CompStats


def generate_candidates(state: GameState, comps: list[CompStats]) -> list[CandidateAction]:
    actions: list[CandidateAction] = [CandidateAction(ActionType.HOLD)]

    owned = {unit.name for unit in state.board + state.bench}
    relevant_units: set[str] = set()
    for comp in comps:
        relevant_units.update(comp.core_units)

    for unit in state.shop:
        if unit.name in owned or unit.name in relevant_units:
            actions.append(
                CandidateAction(
                    ActionType.BUY,
                    target=unit.name,
                    metadata={"cost": unit.cost},
                )
            )

    if state.gold >= 2:
        roll_targets = {max(0, state.gold - 2)}
        for floor in (50, 40, 30, 20, 10, 0):
            if state.gold > floor + 2:
                roll_targets.add(floor)
        for target in sorted(roll_targets, reverse=True):
            actions.append(CandidateAction(ActionType.ROLL, target_gold=target))

    for comp in comps:
        actions.append(CandidateAction(ActionType.PLAY_COMP, target=comp.name))

    return actions
