from __future__ import annotations

from math import exp

from .augments import AugmentCategory, classify_augment, compute_needs
from .models import ActionType, CandidateAction, GameState, ScoreFeature, ScoredAction
from .reliability import DEFAULT_PSEUDOCOUNT, shrunk_value
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
    def __init__(
        self,
        comps: list[CompStats],
        shrinkage_k: float = DEFAULT_PSEUDOCOUNT,
        unit_lookup=None,
    ) -> None:
        self.comps = {comp.name: comp for comp in comps}
        self.shrinkage_k = shrinkage_k
        self.unit_lookup = unit_lookup
        # Field priors are the symmetric constants of an 8-player lobby:
        # mean placement 4.5, top4 0.5, win 1/8. Using constants instead of a
        # computed comp mean keeps a tiny-sample extreme value from dragging
        # its own prior down (which would defeat the shrinkage).
        self.prior_placement = 4.5
        self.prior_top4 = 0.5
        self.prior_win = 0.125

    def score(self, state: GameState, action: CandidateAction) -> ScoredAction:
        if action.action_type == ActionType.PLAY_COMP:
            return self._score_comp(state, action)
        if action.action_type == ActionType.ROLL:
            return self._score_roll(state, action)
        if action.action_type == ActionType.BUY:
            return self._score_buy(state, action)
        if action.action_type == ActionType.CHOOSE_AUGMENT:
            return self._score_augment(state, action)
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
        # Delegates to CompEvaluator so live PLAY_COMP scoring and the
        # comp-analysis surface share one implementation.
        from .comp_eval import CompEvaluator

        evaluator = CompEvaluator(
            list(self.comps.values()),
            unit_lookup=self.unit_lookup,
            shrinkage_k=self.shrinkage_k,
        )
        ev = evaluator.evaluate(state, action.target or "")
        context = sum(f.contribution for f in ev.features)
        return ScoredAction(
            action=action,
            score=ev.score,
            baseline_score=ev.baseline,
            context_score=context,
            confidence=_confidence(ev.score),
            features=ev.features,
            reasons=ev.reasons,
        )

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

        contested = state.contested_unit_count(target)
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
            _feature(
                "unit_contest",
                float(contested),
                -0.05,
                f"{contested} copies held by opponents",
            ),
        ]
        return self._finish(action, 0.0, features)

    def _score_augment(
        self, state: GameState, action: CandidateAction
    ) -> ScoredAction:
        """Rank an augment by which deficit it covers (see augments.py):
        level-behind -> XP, gold-behind -> ECON, items-behind -> ITEM, healthy
        board -> COMBAT, plus comp-synergy boosts."""
        name = action.target or ""
        category = classify_augment(name)
        needs = compute_needs(state, list(self.comps.values()))
        need_by_cat = needs.by_category()
        top = needs.top_need()

        features: list[ScoreFeature] = [
            _feature(
                "need_match",
                need_by_cat.get(category, 0.0),
                0.6,
                (
                    f"{category.value} augment; top deficit is {top.value} "
                    f"(xp~{needs.xp_deficit_gold}g, gold~{needs.gold_deficit:.0f}g, "
                    f"items~{needs.item_deficit:.1f})"
                ),
            ),
        ]

        matching_comps = [c for c in self.comps.values() if name in c.augment_preferences]
        if matching_comps:
            best = min(matching_comps, key=lambda c: c.average_placement)
            features.append(
                _feature(
                    "comp_augment_fit",
                    1.0,
                    0.5,
                    f"Listed as preferred augment for '{best.name}'",
                )
            )

        if category == AugmentCategory.TRAIT:
            board_traits = {t.name.lower() for t in state.traits}
            lowered = name.lower()
            if any(t in lowered for t in board_traits):
                features.append(
                    _feature(
                        "trait_on_board",
                        1.0,
                        0.3,
                        "Emblem/crest matches a trait already on board",
                    )
                )

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
