from __future__ import annotations

from math import exp

from .models import ActionType, CandidateAction, GameState, ScoreFeature, ScoredAction
from .stats import CompStats


def placement_to_score(avg_placement: float) -> float:
    return (4.5 - avg_placement) / 3.5


def _feature(name: str, value: float, weight: float, reason: str) -> ScoreFeature:
    return ScoreFeature(
        name=name,
        value=value,
        weight=weight,
        contribution=value * weight,
        reason=reason,
    )


def _confidence(score: float) -> float:
    # Bounded, monotonic confidence proxy; replace with calibrated confidence later.
    return 1.0 / (1.0 + exp(-abs(score)))


class ActionScorer:
    def __init__(self, comps: list[CompStats]) -> None:
        self.comps = {comp.name: comp for comp in comps}

    def score(self, state: GameState, action: CandidateAction) -> ScoredAction:
        if action.action_type == ActionType.PLAY_COMP:
            return self._score_comp(state, action)
        if action.action_type == ActionType.ROLL:
            return self._score_roll(state, action)
        if action.action_type == ActionType.BUY:
            return self._score_buy(state, action)
        if action.action_type == ActionType.HOLD:
            return self._score_hold(state, action)
        return self._finish(action, 0.0, [])

    def _finish(
        self,
        action: CandidateAction,
        baseline: float,
        features: list[ScoreFeature],
    ) -> ScoredAction:
        context = sum(feature.contribution for feature in features)
        score = baseline + context
        return ScoredAction(
            action=action,
            score=score,
            baseline_score=baseline,
            context_score=context,
            confidence=_confidence(score),
            features=features,
            reasons=[feature.reason for feature in features if feature.contribution != 0],
        )

    def _score_comp(self, state: GameState, action: CandidateAction) -> ScoredAction:
        comp = self.comps[action.target or ""]
        baseline = placement_to_score(comp.average_placement)
        baseline += (comp.top4_rate - 0.50) * 0.50
        baseline += (comp.win_rate - 0.125) * 0.30

        owned = {unit.name for unit in state.board + state.bench}
        overlap = len(owned & comp.core_units)
        overlap_ratio = overlap / len(comp.core_units) if comp.core_units else 0.0
        item_overlap = len(set(state.completed_items) & comp.preferred_items)
        contesters = state.contested_comps.get(comp.name, 0)

        features = [
            _feature(
                "unit_overlap",
                overlap_ratio,
                0.70,
                f"{overlap} core units already owned",
            ),
            _feature(
                "item_fit",
                float(item_overlap),
                0.12,
                f"{item_overlap} preferred completed items",
            ),
            _feature(
                "contest",
                float(contesters),
                -0.22,
                f"{contesters} players contesting this line",
            ),
        ]

        if state.hp <= 30:
            features.append(
                _feature(
                    "low_hp_immediacy",
                    overlap_ratio,
                    0.25,
                    "Low HP rewards lines close to immediate completion",
                )
            )

        return self._finish(action, baseline, features)

    def _score_roll(self, state: GameState, action: CandidateAction) -> ScoredAction:
        target_gold = action.target_gold if action.target_gold is not None else state.gold
        spend = max(0, state.gold - target_gold)
        features: list[ScoreFeature] = []

        if state.hp <= 25:
            features.append(_feature("hp_urgency", 1.0, 0.45, "Critical HP favors stabilization"))
        elif state.hp <= 40:
            features.append(_feature("hp_urgency", 1.0, 0.20, "Low HP favors stabilization"))
        elif state.hp >= 80:
            features.append(_feature("hp_urgency", 1.0, -0.15, "Healthy HP reduces roll urgency"))

        if spend >= 30:
            features.append(_feature("econ_cost", 1.0, -0.18, "Large rolldown spends substantial economy"))
        elif spend >= 20:
            features.append(_feature("econ_cost", 1.0, -0.10, "Moderate rolldown spends economy"))

        if target_gold >= 50:
            features.append(_feature("interest_preservation", 1.0, 0.10, "Preserves maximum interest"))

        return self._finish(action, 0.0, features)

    def _score_buy(self, state: GameState, action: CandidateAction) -> ScoredAction:
        target = action.target or ""
        copies_owned = sum(1 for unit in state.board + state.bench if unit.name == target)
        relevant_comp_count = sum(1 for comp in self.comps.values() if target in comp.core_units)
        cost = int(action.metadata.get("cost", 0))

        features = [
            _feature(
                "upgrade_potential",
                1.0 if copies_owned else 0.0,
                0.25,
                "Already owns a copy; purchase improves upgrade potential",
            ),
            _feature(
                "comp_flexibility",
                min(float(relevant_comp_count), 4.0),
                0.08,
                f"Unit appears in {relevant_comp_count} candidate comps",
            ),
            _feature(
                "low_gold_purchase_cost",
                1.0 if state.gold - cost < 10 else 0.0,
                -0.08,
                "Purchase reduces low-gold flexibility",
            ),
        ]
        return self._finish(action, 0.0, features)

    def _score_hold(self, state: GameState, action: CandidateAction) -> ScoredAction:
        features = [
            _feature(
                "max_interest",
                1.0 if state.gold >= 50 else 0.0,
                0.18,
                "Holding preserves maximum interest",
            ),
            _feature(
                "healthy_hp_greed",
                1.0 if state.hp >= 70 else 0.0,
                0.12,
                "Healthy HP permits greed",
            ),
            _feature(
                "critical_hp_risk",
                1.0 if state.hp <= 25 else 0.0,
                -0.35,
                "Critical HP makes holding dangerous",
            ),
        ]
        return self._finish(action, 0.0, features)
