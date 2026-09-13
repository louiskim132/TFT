from __future__ import annotations

from tft_engine import CompStats, DecisionEngine, GameState, InMemoryStatsProvider, ShopUnit, UnitState


provider = InMemoryStatsProvider(
    comps=[
        CompStats(
            name="Comp A",
            average_placement=3.92,
            top4_rate=0.57,
            win_rate=0.15,
            play_rate=0.08,
            core_units=frozenset({"Unit A", "Unit B", "Unit C", "Unit D"}),
            preferred_items=frozenset({"Item 1", "Item 2"}),
        ),
        CompStats(
            name="Comp B",
            average_placement=4.08,
            top4_rate=0.53,
            win_rate=0.13,
            play_rate=0.05,
            core_units=frozenset({"Unit B", "Unit E", "Unit F", "Unit G"}),
            preferred_items=frozenset({"Item 2", "Item 3"}),
        ),
    ]
)

state = GameState(
    patch="test",
    stage="3-5",
    hp=48,
    gold=38,
    level=7,
    board=[UnitState("Unit B", 2), UnitState("Unit E", 2), UnitState("Unit F", 1)],
    bench=[UnitState("Unit G", 1)],
    shop=[ShopUnit("Unit A", 3), ShopUnit("Unit F", 3), ShopUnit("Random Unit", 2)],
    completed_items=["Item 2", "Item 3"],
    contested_comps={"Comp A": 2, "Comp B": 0},
)

result = DecisionEngine(provider).decide(state)
print(f"Decision computed in {result.latency_ms:.3f} ms from {result.candidate_count} candidates\n")
for i, scored in enumerate(result.actions, start=1):
    action = scored.action
    label = action.action_type.value
    if action.target:
        label += f" -> {action.target}"
    if action.target_gold is not None:
        label += f" to {action.target_gold}g"
    print(f"{i}. {label}: {scored.score:+.3f} (confidence {scored.confidence:.2%})")
    for reason in scored.reasons:
        print(f"   - {reason}")
