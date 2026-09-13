from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CompStats:
    name: str
    average_placement: float
    top4_rate: float
    win_rate: float
    play_rate: float
    core_units: frozenset[str]
    preferred_items: frozenset[str]


@dataclass(frozen=True)
class UnitStats:
    name: str
    average_placement: float
    top4_rate: float


@dataclass(frozen=True)
class ItemStats:
    name: str
    average_placement: float
    top4_rate: float


class StatsProvider(Protocol):
    def get_comps(self, patch: str) -> list[CompStats]: ...
    def get_unit(self, patch: str, name: str) -> UnitStats | None: ...
    def get_item(self, patch: str, name: str) -> ItemStats | None: ...


class InMemoryStatsProvider:
    """Development/test provider. Live play should read from a local cache."""

    def __init__(
        self,
        comps: list[CompStats],
        units: list[UnitStats] | None = None,
        items: list[ItemStats] | None = None,
    ) -> None:
        self._comps = list(comps)
        self._units = {item.name: item for item in (units or [])}
        self._items = {item.name: item for item in (items or [])}

    def get_comps(self, patch: str) -> list[CompStats]:
        return list(self._comps)

    def get_unit(self, patch: str, name: str) -> UnitStats | None:
        return self._units.get(name)

    def get_item(self, patch: str, name: str) -> ItemStats | None:
        return self._items.get(name)
