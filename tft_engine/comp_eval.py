"""Composition evaluation: how well does the current GameState fit each comp?

Produces a per-comp breakdown of named feature contributions so the result is
inspectable ("why did Comp A rank above Comp B") and reusable as an ML
training table later. This is the same logic the live path uses for PLAY_COMP
candidates — CompEvaluator is the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .models import GameState, ScoreFeature
from .reliability import DEFAULT_PSEUDOCOUNT, shrunk_value
from .scoring import placement_to_score
from .stats import CompStats, StatsProvider, UnitStats

UnitLookup = Callable[[str], "UnitStats | None"]


def _feature(name: str, value: float, weight: float, reason: str) -> ScoreFeature:
    return ScoreFeature(
        name=name, value=value, weight=weight, contribution=value * weight,
        reason=reason,
    )


@dataclass
class CompEvaluation:
    name: str
    score: float
    baseline: float  # shrunk meta prior
    context: float
    features: list[ScoreFeature] = field(default_factory=list)

    @property
    def reasons(self) -> list[str]:
        return [f.reason for f in self.features if f.contribution != 0]


class CompEvaluator:
    def __init__(
        self,
        comps: list[CompStats],
        unit_lookup: UnitLookup | None = None,
        shrinkage_k: float = DEFAULT_PSEUDOCOUNT,
    ) -> None:
        self.comps = {c.name: c for c in comps}
        self.unit_lookup = unit_lookup or (lambda name: None)
        self.k = shrinkage_k
        # Symmetric lobby constants — see scoring.ActionScorer.
        self.prior_placement = 4.5
        self.prior_top4 = 0.5
        self.prior_win = 0.125

    def meta_baseline(self, comp: CompStats) -> float:
        n = comp.sample_size
        ap = shrunk_value(comp.average_placement, n, self.prior_placement, self.k)
        t4 = shrunk_value(comp.top4_rate, n, self.prior_top4, self.k)
        wr = shrunk_value(comp.win_rate, n, self.prior_win, self.k)
        return (
            placement_to_score(ap)
            + (t4 - 0.50) * 0.50
            + (wr - 0.125) * 0.30
        )

    def evaluate(self, state: GameState, comp_name: str) -> CompEvaluation:
        comp = self.comps[comp_name]
        baseline = self.meta_baseline(comp)
        n = comp.sample_size

        owned = {u.name: u for u in state.board + state.bench}
        fielded = {u.name for u in state.board}
        core = comp.core_units
        core_owned = set(owned) & core
        optional_owned = set(owned) & comp.optional_units
        overlap_ratio = len(core_owned) / len(core) if core else 0.0
        upgraded = sum(
            1 for u in core_owned if owned[u].star_level >= 2
        )
        item_overlap = len(set(state.completed_items) & comp.preferred_items)

        # Estimated gold to complete the core: sum of missing core unit costs.
        missing_cost = 0
        known = 0
        for unit_name in core - set(owned):
            stats = self.unit_lookup(unit_name)
            if stats and stats.cost:
                missing_cost += stats.cost
                known += 1
        if known < len(core - set(owned)):
            missing_cost += (len(core - set(owned)) - known) * 3  # assume mid cost

        # Level gap: comps that want a higher level than the player's are
        # expensive to reach now.
        level_gap = 0.0
        if comp.typical_level is not None:
            level_gap = max(0.0, float(comp.typical_level - state.level))

        # Contest: explicit lobby summary plus per-opponent signals.
        contesters = state.contested_comps.get(comp.name, 0) + sum(
            1 for o in state.opponents if o.likely_comp == comp.name
        )

        # Transition cost: share of the current board that is dead weight for
        # this comp (not core, not optional).
        if fielded:
            dead = sum(
                1 for u in fielded if u not in core and u not in comp.optional_units
            )
            dead_ratio = dead / len(fielded)
        else:
            dead_ratio = 0.0

        # Trait continuity: comp traits already active on board.
        comp_traits: set[str] = set()
        for unit_name in core:
            stats = self.unit_lookup(unit_name)
            if stats:
                comp_traits.update(stats.traits)
        active_traits = {t.name for t in state.traits}
        trait_continuity = (
            len(comp_traits & active_traits) / len(comp_traits) if comp_traits else 0.0
        )

        features = [
            _feature(
                "sample_reliability",
                n / (n + self.k) if (n + self.k) else 0.0,
                0.0,  # recorded for future learning; shrinkage already applied
                f"{n} recorded games",
            ),
            _feature(
                "core_unit_overlap",
                overlap_ratio,
                0.70,
                f"{len(core_owned)}/{len(core)} core units owned",
            ),
            _feature(
                "upgraded_core_overlap",
                upgraded / len(core) if core else 0.0,
                0.35,
                f"{upgraded} core units already 2-star+",
            ),
            _feature(
                "optional_unit_overlap",
                len(optional_owned) / len(comp.optional_units)
                if comp.optional_units
                else 0.0,
                0.10,
                f"{len(optional_owned)} optional units owned",
            ),
            _feature(
                "item_fit",
                item_overlap / len(comp.preferred_items)
                if comp.preferred_items
                else 0.0,
                0.35,
                f"{item_overlap} preferred completed items",
            ),
            _feature(
                "trait_continuity",
                trait_continuity,
                0.15,
                f"{len(comp_traits & active_traits)}/{len(comp_traits)} comp traits already active",
            ),
            _feature(
                "gold_cost_to_core",
                min(float(missing_cost), 40.0),
                -0.012,
                f"~{missing_cost}g to buy missing core units",
            ),
            _feature(
                "level_gap",
                level_gap,
                -0.08,
                f"comp wants level {comp.typical_level}, player at {state.level}"
                if comp.typical_level
                else "no typical level recorded",
            ),
            _feature(
                "contest",
                float(contesters),
                -0.22,
                f"{contesters} players contesting this line",
            ),
            _feature(
                "transition_cost",
                dead_ratio,
                -0.30,
                f"{dead_ratio:.0%} of current board unused by this comp",
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

        context = sum(f.contribution for f in features)
        return CompEvaluation(
            name=comp.name,
            score=baseline + context,
            baseline=baseline,
            context=context,
            features=features,
        )

    def evaluate_all(
        self, state: GameState, top_n: int | None = None
    ) -> list[CompEvaluation]:
        ranked = sorted(
            (self.evaluate(state, name) for name in self.comps),
            key=lambda e: e.score,
            reverse=True,
        )
        return ranked[:top_n] if top_n else ranked


def evaluate_comps(
    state: GameState,
    provider: StatsProvider,
    top_n: int = 5,
) -> list[CompEvaluation]:
    """Convenience wrapper: rank compositions for a state against a provider's
    cached patch data."""
    comps = provider.get_comps(state.patch)
    evaluator = CompEvaluator(
        comps,
        unit_lookup=lambda name: provider.get_unit(state.patch, name),
    )
    return evaluator.evaluate_all(state, top_n=top_n)
