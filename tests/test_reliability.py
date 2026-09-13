from tft_engine import CompStats, DecisionEngine, GameState, InMemoryStatsProvider
from tft_engine.models import ActionType
from tft_engine.reliability import shrinkage_weight, shrunk_value
from tft_engine.scoring import ActionScorer


def _comp(name: str, avg: float, n: int) -> CompStats:
    return CompStats(
        name=name,
        average_placement=avg,
        top4_rate=0.5,
        win_rate=0.1,
        play_rate=0.05,
        core_units=frozenset({"X"}),
        preferred_items=frozenset(),
        sample_size=n,
    )


def test_shrinkage_weight_bounds() -> None:
    assert shrinkage_weight(0) == 0.0
    assert shrinkage_weight(250) == 0.5
    assert 0.0 < shrinkage_weight(10) < shrinkage_weight(10000) < 1.0


def test_shrunk_value_pulls_toward_prior() -> None:
    prior = 4.5
    small = shrunk_value(2.0, sample_size=25, prior=prior)
    huge = shrunk_value(4.0, sample_size=50000, prior=prior)
    assert abs(huge - 4.0) < 0.05
    assert small > 4.2  # extreme 2.0 barely moves off the prior


def test_tiny_sample_extreme_does_not_outrank_large_sample() -> None:
    tiny_hot = _comp("TinyHot", avg=2.9, n=40)
    big_solid = _comp("BigSolid", avg=4.0, n=50000)
    scorer = ActionScorer([tiny_hot, big_solid])
    state = GameState(patch="t", stage="3-5", hp=50, gold=20, level=7)

    tiny = scorer.score(state, _action("TinyHot"))
    big = scorer.score(state, _action("BigSolid"))
    assert big.score > tiny.score


def _action(name: str):
    from tft_engine.models import CandidateAction

    return CandidateAction(ActionType.PLAY_COMP, target=name)


def test_zero_sample_falls_back_to_prior() -> None:
    unknown = _comp("Unknown", avg=1.5, n=0)
    solid = _comp("Solid", avg=4.0, n=30000)
    scorer = ActionScorer([unknown, solid])
    state = GameState(patch="t", stage="3-5", hp=50, gold=20, level=7)
    # n=0 -> baseline uses the field prior, not the suspicious 1.5.
    assert scorer.score(state, _action("Solid")).score > scorer.score(
        state, _action("Unknown")
    ).score


def test_engine_integration_prefers_reliable_comp() -> None:
    provider = InMemoryStatsProvider(comps=[_comp("TinyHot", 2.9, 40), _comp("BigSolid", 4.0, 50000)])
    state = GameState(patch="t", stage="3-5", hp=50, gold=20, level=7)
    result = DecisionEngine(provider, max_results=10).decide(state)
    comp_actions = [a for a in result.actions if a.action.action_type == ActionType.PLAY_COMP]
    assert comp_actions[0].action.target == "BigSolid"


def test_reliability_recorded_in_feature_vector() -> None:
    comp = _comp("Solid", 4.0, 50000)
    scorer = ActionScorer([comp])
    state = GameState(patch="t", stage="3-5", hp=50, gold=20, level=7)
    scored = scorer.score(state, _action("Solid"))
    rel = next(f for f in scored.features if f.name == "sample_reliability")
    assert rel.value > 0.99
    assert rel.weight == 0.0  # recorded for future learning, not double-counted
