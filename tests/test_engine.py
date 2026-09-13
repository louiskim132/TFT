from tft_engine import CompStats, DecisionEngine, GameState, InMemoryStatsProvider, ShopUnit, UnitState
from tft_engine.models import ActionType


def provider() -> InMemoryStatsProvider:
    return InMemoryStatsProvider(
        comps=[
            CompStats(
                name="Contested",
                average_placement=3.8,
                top4_rate=0.58,
                win_rate=0.15,
                play_rate=0.10,
                core_units=frozenset({"A", "B", "C", "D"}),
                preferred_items=frozenset({"Sword Item"}),
            ),
            CompStats(
                name="Natural",
                average_placement=4.1,
                top4_rate=0.52,
                win_rate=0.12,
                play_rate=0.06,
                core_units=frozenset({"E", "F", "G", "H"}),
                preferred_items=frozenset({"Bow Item", "Glove Item"}),
            ),
        ]
    )


def test_context_can_overcome_better_raw_meta_comp() -> None:
    state = GameState(
        patch="test",
        stage="3-5",
        hp=48,
        gold=38,
        level=7,
        board=[UnitState("E", 2), UnitState("F", 2), UnitState("G", 1)],
        bench=[UnitState("H", 1)],
        completed_items=["Bow Item", "Glove Item"],
        contested_comps={"Contested": 2, "Natural": 0},
    )
    result = DecisionEngine(provider(), max_results=20).decide(state)
    comp_actions = [x for x in result.actions if x.action.action_type == ActionType.PLAY_COMP]
    assert comp_actions[0].action.target == "Natural"
    assert comp_actions[0].score > comp_actions[1].score


def test_candidate_generator_ignores_irrelevant_shop_unit() -> None:
    state = GameState(
        patch="test",
        stage="2-5",
        hp=90,
        gold=20,
        level=5,
        shop=[ShopUnit("E", 2), ShopUnit("Irrelevant", 1)],
    )
    result = DecisionEngine(provider(), max_results=50).decide(state)
    bought = {
        action.action.target
        for action in result.actions
        if action.action.action_type == ActionType.BUY
    }
    assert "E" in bought
    assert "Irrelevant" not in bought


def test_low_hp_penalizes_hold_relative_to_roll() -> None:
    state = GameState(
        patch="test",
        stage="4-2",
        hp=20,
        gold=40,
        level=7,
    )
    result = DecisionEngine(provider(), max_results=50).decide(state)
    hold = next(x for x in result.actions if x.action.action_type == ActionType.HOLD)
    rolls = [x for x in result.actions if x.action.action_type == ActionType.ROLL]
    assert rolls
    assert max(x.score for x in rolls) > hold.score


def test_decision_result_reports_latency_and_candidate_count() -> None:
    state = GameState(patch="test", stage="2-1", hp=100, gold=10, level=4)
    result = DecisionEngine(provider()).decide(state)
    assert result.latency_ms >= 0
    assert result.candidate_count >= len(result.actions)
