import pytest

from tft_engine import (
    SCHEMA_VERSION,
    GameState,
    StateValidationError,
    UnitState,
    game_state_from_dict,
    game_state_to_dict,
    validate_game_state,
)

FULL_STATE = {
    "schema_version": 1,
    "patch": "15.5",
    "set": "15",
    "stage": "3-5",
    "hp": 48,
    "gold": 38,
    "level": 7,
    "xp": 12,
    "streak": -2,
    "board": [
        {"name": "Unit B", "star_level": 2, "items": ["Item 2"], "position": [0, 3]},
        {"name": "Unit E", "star_level": 2, "position": {"row": 1, "col": 0}},
        {"name": "Unit F"},
    ],
    "bench": [{"name": "Unit G"}],
    "shop": [{"name": "Unit A", "cost": 3}, {"name": "Unit F", "cost": 3}],
    "components": ["Bow", "Sword"],
    "completed_items": ["Item 2", "Item 3"],
    "consumables": ["Reforger"],
    "augments": ["Augment 1"],
    "traits": [{"name": "Bruiser", "count": 4}, {"name": "Sniper", "count": 2}],
    "contested_comps": {"Comp A": 2},
    "contested_units": {"Unit A": 3},
    "opponents": [
        {
            "id": "opp-3",
            "hp": 61,
            "level": 7,
            "units": [{"name": "Unit A", "star_level": 2}],
            "likely_comp": "Comp A",
            "contested_units": ["Unit C"],
            "last_seen_stage": "3-4",
        }
    ],
    "history": [
        {"stage": "3-4", "result": "loss", "damage_taken": 11, "opponent_id": "opp-3"}
    ],
    "interest": 3,
    "streak_income": 1,
    "state_confidence": 0.9,
}


def test_round_trip_full_state() -> None:
    state = game_state_from_dict(FULL_STATE)
    payload = game_state_to_dict(state)
    state2 = game_state_from_dict(payload)
    assert state2 == state
    assert payload["schema_version"] == SCHEMA_VERSION


def test_round_trip_minimal_state() -> None:
    state = GameState(patch="15.5", stage="2-1", hp=100, gold=10, level=4)
    assert game_state_from_dict(game_state_to_dict(state)) == state


def test_v1_payload_without_version_parses() -> None:
    payload = {"patch": "15.5", "stage": "3-5", "hp": 48, "gold": 38, "level": 7}
    state = game_state_from_dict(payload)
    assert state.schema_version == 1
    assert state.streak == 0
    assert state.opponents == []


def test_newer_version_rejected() -> None:
    with pytest.raises(StateValidationError):
        game_state_from_dict({**FULL_STATE, "schema_version": SCHEMA_VERSION + 1})


def test_missing_required_field_rejected() -> None:
    for key in ("patch", "stage", "hp", "gold", "level"):
        bad = {k: v for k, v in FULL_STATE.items() if k != key}
        with pytest.raises(StateValidationError, match=key):
            game_state_from_dict(bad)


def test_malformed_shop_entry_rejected() -> None:
    with pytest.raises(StateValidationError):
        game_state_from_dict({**FULL_STATE, "shop": [{"name": "Unit A"}]})


def test_positions_parse_both_forms() -> None:
    state = game_state_from_dict(FULL_STATE)
    assert state.board[0].position == (0, 3)
    assert state.board[1].position == (1, 0)
    assert state.board[2].position is None


def test_opponent_contested_units_merge_with_summary() -> None:
    state = game_state_from_dict(FULL_STATE)
    assert state.contested_unit_count("Unit A") == 3 + 1
    assert state.contested_unit_count("Unit C") == 1
    assert state.contested_unit_count("Nobody") == 0


def test_validate_flags_bad_values() -> None:
    state = game_state_from_dict({**FULL_STATE, "level": 12, "stage": "banana"})
    issues = validate_game_state(state)
    assert any("level" in i for i in issues)
    assert any("stage" in i for i in issues)


def test_validate_clean_state_has_no_issues() -> None:
    state = game_state_from_dict(FULL_STATE)
    assert validate_game_state(state) == []


def test_state_confidence_preserved() -> None:
    state = game_state_from_dict(FULL_STATE)
    assert state.state_confidence == 0.9
    assert game_state_from_dict({"patch": "p", "stage": "1-1", "hp": 1, "gold": 0, "level": 1}).state_confidence == 1.0


def test_history_result_must_be_win_or_loss() -> None:
    bad = {**FULL_STATE, "history": [{"stage": "3-4", "result": "draw"}]}
    with pytest.raises(StateValidationError):
        game_state_from_dict(bad)
