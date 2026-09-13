"""Need-based augment selection: classification, deficits, scoring."""

from __future__ import annotations

from tft_engine.augments import AugmentCategory, classify_augment, compute_needs
from tft_engine.engine import DecisionEngine
from tft_engine.models import GameState, TraitState, UnitState
from tft_engine.stats import CompStats, InMemoryStatsProvider


def _comp(**kw) -> CompStats:
    return CompStats(
        name=kw.get("name", "Comp"),
        average_placement=3.5,
        top4_rate=0.6,
        win_rate=0.12,
        play_rate=0.1,
        sample_size=1000,
        core_units=frozenset(kw.get("units", ())),
        preferred_items=frozenset(),
        patch="18.1",
        source="test",
        retrieved_at="2026-09-13T00:00:00+00:00",
        augment_preferences=frozenset(kw.get("augs", ())),
        typical_level=kw.get("lvl"),
    )


def _state(**kw) -> GameState:
    base = dict(patch="18.1", stage="3-2", hp=80, gold=40, level=6)
    base.update(kw)
    return GameState(**base)


def test_classify_known_categories():
    assert classify_augment("Rich Get Richer") == AugmentCategory.ECON
    assert classify_augment("Level Up!") == AugmentCategory.XP
    assert classify_augment("Component Grab Bag") == AugmentCategory.ITEM
    assert classify_augment("Spellweaver Emblem") == AugmentCategory.TRAIT
    assert classify_augment("Pandora's Items") == AugmentCategory.ITEM
    # Unmatched names default to combat, not an error.
    assert classify_augment("Sundered Strikes") == AugmentCategory.COMBAT


def test_level_deficit_drives_xp_need():
    # 3-2 expects lvl 6; a lvl-4 player is two levels behind (10+20 = 30g of XP).
    needs = compute_needs(
        _state(level=4, gold=50, completed_items=["a", "b", "c"])
    )
    assert needs.xp_deficit_gold == 30
    assert needs.top_need() == AugmentCategory.XP


def test_gold_deficit_drives_econ_need():
    needs = compute_needs(
        _state(level=6, gold=5, completed_items=["a", "b", "c"])
    )
    assert needs.gold_deficit > 20
    assert needs.top_need() == AugmentCategory.ECON


def test_item_deficit_drives_item_need():
    needs = compute_needs(_state(level=6, gold=50, completed_items=[], components=[]))
    assert needs.item_deficit > 0
    assert needs.top_need() == AugmentCategory.ITEM


def test_healthy_state_defaults_to_combat():
    needs = compute_needs(
        _state(
            level=6,
            gold=50,
            completed_items=["a", "b", "c"],
            components=["x", "y"],
        )
    )
    assert needs.top_need() == AugmentCategory.COMBAT


def test_slow_roll_comp_caps_expected_level():
    # On a Slow-Roll(5) line, sitting at 5 in stage 3 is on-plan, not behind.
    needs = compute_needs(
        _state(
            stage="3-2",
            level=5,
            board=[UnitState("Rek'Sai")],
        ),
        comps=[_comp(units=("Rek'Sai",), lvl=5)],
    )
    assert needs.expected_level == 5
    assert needs.xp_deficit_gold == 0


def test_engine_ranks_matching_augment_first():
    comps = [_comp(units=("Rek'Sai",), augs=("Riftwalk",))]
    engine = DecisionEngine(InMemoryStatsProvider(comps=comps))
    # Behind on gold; comp-listed augment beats raw econ, econ beats combat.
    state = _state(
        level=6,
        gold=5,
        completed_items=["a", "b", "c"],
        augment_choices=["Rich Get Richer", "Sundered Strikes", "Riftwalk"],
    )
    result = engine.decide(state)
    aug_actions = [
        a for a in result.actions if a.action.action_type.value == "choose_augment"
    ]
    assert aug_actions, "no augment candidates generated"
    assert aug_actions[0].action.target == "Riftwalk"  # comp fit beats raw econ
    assert aug_actions[1].action.target == "Rich Get Richer"


def test_augment_choices_round_trip():
    from tft_engine.state_io import game_state_from_dict, game_state_to_dict

    state = _state(augment_choices=["Rich Get Richer", "Level Up!"])
    restored = game_state_from_dict(game_state_to_dict(state))
    assert restored.augment_choices == ["Rich Get Richer", "Level Up!"]
