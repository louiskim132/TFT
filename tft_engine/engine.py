from __future__ import annotations

from time import perf_counter

from .candidates import generate_candidates
from .models import DecisionResult, GameState
from .scoring import ActionScorer
from .stats import StatsProvider


class DecisionEngine:
    def __init__(self, stats_provider: StatsProvider, max_results: int = 5) -> None:
        self.stats_provider = stats_provider
        self.max_results = max_results

    def decide(self, state: GameState) -> DecisionResult:
        started = perf_counter()
        comps = self.stats_provider.get_comps(state.patch)
        candidates = generate_candidates(state, comps)
        scorer = ActionScorer(comps)
        scored = [scorer.score(state, action) for action in candidates]
        scored.sort(key=lambda item: item.score, reverse=True)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return DecisionResult(
            actions=scored[: self.max_results],
            latency_ms=elapsed_ms,
            candidate_count=len(candidates),
        )
