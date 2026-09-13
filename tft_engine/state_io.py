"""Canonical GameState <-> JSON boundary.

Serialization is explicit (not asdict) so the wire format stays stable as the
internal model evolves. `schema_version` is embedded in every serialized state;
payloads older than the current version are migrated on read, and payloads from
a newer version are rejected rather than silently misparsed.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .models import (
    SCHEMA_VERSION,
    CombatRecord,
    GameState,
    OpponentState,
    ShopUnit,
    TraitState,
    UnitState,
)

_STAGE_RE = re.compile(r"^\d+-\d+$")


class StateValidationError(ValueError):
    """Raised when a payload cannot be interpreted as a GameState."""


def _req(payload: Mapping[str, Any], key: str) -> Any:
    if key not in payload:
        raise StateValidationError(f"missing required field '{key}'")
    return payload[key]


def _int(payload: Mapping[str, Any], key: str, default: int | None = None) -> int:
    value = payload.get(key, default)
    if value is None:
        raise StateValidationError(f"field '{key}' is required")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise StateValidationError(f"field '{key}' must be an integer") from None


def _opt_int(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise StateValidationError(f"field '{key}' must be an integer") from None


def _str_list(raw: Any, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise StateValidationError(f"field '{field_name}' must be a list")
    return [str(item) for item in raw]


def _position(raw: Any, field_name: str) -> tuple[int, int] | None:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return (int(raw["row"]), int(raw["col"]))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return (int(raw[0]), int(raw[1]))
    raise StateValidationError(
        f"field '{field_name}.position' must be [row, col] or {{'row': r, 'col': c}}"
    )


def _unit(raw: Any, field_name: str) -> UnitState:
    if isinstance(raw, str):
        return UnitState(name=raw)
    if not isinstance(raw, Mapping):
        raise StateValidationError(f"entries of '{field_name}' must be objects")
    if "name" not in raw:
        raise StateValidationError(f"entries of '{field_name}' require 'name'")
    return UnitState(
        name=str(raw["name"]),
        star_level=_int(raw, "star_level", 1),
        items=tuple(_str_list(raw.get("items"), f"{field_name}.items")),
        position=_position(raw.get("position"), field_name),
    )


def _units(raw: Any, field_name: str) -> list[UnitState]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise StateValidationError(f"field '{field_name}' must be a list")
    return [_unit(item, f"{field_name}[{i}]") for i, item in enumerate(raw)]


def _shop(raw: Any) -> list[ShopUnit]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise StateValidationError("field 'shop' must be a list")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping) or "name" not in item or "cost" not in item:
            raise StateValidationError(f"entries of 'shop' require 'name' and 'cost'")
        out.append(ShopUnit(name=str(item["name"]), cost=int(item["cost"])))
    return out


def _traits(raw: Any) -> list[TraitState]:
    if raw is None:
        return []
    if isinstance(raw, Mapping):  # {"Bruiser": 4, ...}
        return [TraitState(name=str(k), count=int(v)) for k, v in raw.items()]
    out = []
    for item in raw:
        if isinstance(item, str):
            out.append(TraitState(name=item, count=0))
        elif isinstance(item, Mapping) and "name" in item:
            out.append(TraitState(name=str(item["name"]), count=int(item.get("count", 0))))
        else:
            raise StateValidationError("entries of 'traits' require 'name'")
    return out


def _opponents(raw: Any) -> list[OpponentState]:
    if raw is None:
        return []
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping) or "id" not in item:
            raise StateValidationError("entries of 'opponents' require 'id'")
        out.append(
            OpponentState(
                id=str(item["id"]),
                hp=_opt_int(item, "hp"),
                level=_opt_int(item, "level"),
                observed_units=_units(item.get("units"), f"opponents[{i}].units"),
                known_items=_str_list(item.get("known_items"), "opponents.known_items"),
                likely_comp=(str(item["likely_comp"]) if item.get("likely_comp") else None),
                contested_units=frozenset(
                    _str_list(item.get("contested_units"), "opponents.contested_units")
                ),
                last_seen_stage=(
                    str(item["last_seen_stage"]) if item.get("last_seen_stage") else None
                ),
            )
        )
    return out


def _history(raw: Any) -> list[CombatRecord]:
    if raw is None:
        return []
    out = []
    for item in raw:
        if not isinstance(item, Mapping) or "stage" not in item or "result" not in item:
            raise StateValidationError("entries of 'history' require 'stage' and 'result'")
        result = str(item["result"])
        if result not in ("win", "loss"):
            raise StateValidationError("history 'result' must be 'win' or 'loss'")
        out.append(
            CombatRecord(
                stage=str(item["stage"]),
                result=result,
                damage_taken=int(item.get("damage_taken", 0)),
                opponent_id=(str(item["opponent_id"]) if item.get("opponent_id") else None),
            )
        )
    return out


def game_state_from_dict(payload: Mapping[str, Any]) -> GameState:
    if not isinstance(payload, Mapping):
        raise StateValidationError("game state payload must be an object")
    version = _int(payload, "schema_version", SCHEMA_VERSION)
    if version > SCHEMA_VERSION:
        raise StateValidationError(
            f"schema_version {version} is newer than supported {SCHEMA_VERSION}"
        )
    return GameState(
        patch=str(_req(payload, "patch")),
        stage=str(_req(payload, "stage")),
        hp=_int(payload, "hp"),
        gold=_int(payload, "gold"),
        level=_int(payload, "level"),
        xp=_int(payload, "xp", 0),
        board=_units(payload.get("board"), "board"),
        bench=_units(payload.get("bench"), "bench"),
        shop=_shop(payload.get("shop")),
        components=_str_list(payload.get("components"), "components"),
        completed_items=_str_list(payload.get("completed_items"), "completed_items"),
        augments=_str_list(payload.get("augments"), "augments"),
        augment_choices=_str_list(
            payload.get("augment_choices"), "augment_choices"
        ),
        contested_comps={
            str(k): int(v) for k, v in (payload.get("contested_comps") or {}).items()
        },
        contested_units={
            str(k): int(v) for k, v in (payload.get("contested_units") or {}).items()
        },
        schema_version=version,
        set=(str(payload["set"]) if payload.get("set") else None),
        streak=_int(payload, "streak", 0),
        consumables=_str_list(payload.get("consumables"), "consumables"),
        traits=_traits(payload.get("traits")),
        opponents=_opponents(payload.get("opponents")),
        history=_history(payload.get("history")),
        interest=_opt_int(payload, "interest"),
        streak_income=_opt_int(payload, "streak_income"),
        state_confidence=float(payload.get("state_confidence", 1.0)),
    )


def _unit_to_dict(unit: UnitState) -> dict[str, Any]:
    out: dict[str, Any] = {"name": unit.name, "star_level": unit.star_level}
    if unit.items:
        out["items"] = list(unit.items)
    if unit.position is not None:
        out["position"] = [unit.position[0], unit.position[1]]
    return out


def game_state_to_dict(state: GameState) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "patch": state.patch,
        "stage": state.stage,
        "hp": state.hp,
        "gold": state.gold,
        "level": state.level,
        "xp": state.xp,
        "board": [_unit_to_dict(u) for u in state.board],
        "bench": [_unit_to_dict(u) for u in state.bench],
        "shop": [{"name": u.name, "cost": u.cost} for u in state.shop],
    }
    if state.set:
        out["set"] = state.set
    if state.streak:
        out["streak"] = state.streak
    for name in (
        "components",
        "completed_items",
        "augments",
        "augment_choices",
        "consumables",
    ):
        value = getattr(state, name)
        if value:
            out[name] = list(value)
    if state.contested_comps:
        out["contested_comps"] = dict(state.contested_comps)
    if state.contested_units:
        out["contested_units"] = dict(state.contested_units)
    if state.traits:
        out["traits"] = [{"name": t.name, "count": t.count} for t in state.traits]
    if state.opponents:
        out["opponents"] = [
            {
                "id": o.id,
                **({"hp": o.hp} if o.hp is not None else {}),
                **({"level": o.level} if o.level is not None else {}),
                **(
                    {"units": [_unit_to_dict(u) for u in o.observed_units]}
                    if o.observed_units
                    else {}
                ),
                **({"known_items": list(o.known_items)} if o.known_items else {}),
                **({"likely_comp": o.likely_comp} if o.likely_comp else {}),
                **(
                    {"contested_units": sorted(o.contested_units)}
                    if o.contested_units
                    else {}
                ),
                **(
                    {"last_seen_stage": o.last_seen_stage}
                    if o.last_seen_stage
                    else {}
                ),
            }
            for o in state.opponents
        ]
    if state.history:
        out["history"] = [
            {
                "stage": r.stage,
                "result": r.result,
                "damage_taken": r.damage_taken,
                **({"opponent_id": r.opponent_id} if r.opponent_id else {}),
            }
            for r in state.history
        ]
    if state.interest is not None:
        out["interest"] = state.interest
    if state.streak_income is not None:
        out["streak_income"] = state.streak_income
    if state.state_confidence != 1.0:
        out["state_confidence"] = state.state_confidence
    return out


def validate_game_state(state: GameState) -> list[str]:
    """Soft sanity checks; returns issues instead of raising so borderline
    states can still be scored while surfacing suspicion upstream."""
    issues: list[str] = []
    if not _STAGE_RE.match(state.stage):
        issues.append(f"stage '{state.stage}' does not match '<round>-<phase>'")
    if not 1 <= state.level <= 10:
        issues.append(f"level {state.level} outside 1-10")
    if not 0 <= state.hp <= 100:
        issues.append(f"hp {state.hp} outside 0-100")
    if state.gold < 0:
        issues.append(f"gold {state.gold} is negative")
    for unit in state.board + state.bench:
        if not 1 <= unit.star_level <= 4:
            issues.append(f"{unit.name} star_level {unit.star_level} outside 1-4")
        if unit.position is not None:
            row, col = unit.position
            if not (0 <= row <= 3 and 0 <= col <= 6):
                issues.append(f"{unit.name} position {(row, col)} off 4x7 board")
    for unit in state.shop:
        if not 1 <= unit.cost <= 5:
            issues.append(f"shop unit {unit.name} cost {unit.cost} outside 1-5")
    if len(state.board) > 10:
        issues.append("board exceeds maximum unit slots")
    return issues
