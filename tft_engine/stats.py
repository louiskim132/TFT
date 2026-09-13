"""Normalized knowledge schema.

Every statistical record carries provenance (source, retrieved_at), scope
(patch, rank_bucket, region where relevant), and sample_size so downstream
scoring can apply reliability adjustments. These types are provider-neutral:
no field names or semantics borrowed from a specific upstream source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    patch: str = ""
    composition_id: str | None = None
    rank_bucket: str | None = None
    region: str | None = None
    sample_size: int = 0
    source: str = ""
    retrieved_at: str = ""
    optional_units: frozenset[str] = frozenset()
    augment_preferences: frozenset[str] = frozenset()
    typical_level: int | None = None


@dataclass(frozen=True)
class UnitStats:
    name: str
    average_placement: float = 0.0
    top4_rate: float = 0.0
    patch: str = ""
    win_rate: float = 0.0
    play_rate: float = 0.0
    star_level: int | None = None  # None = aggregated across stars
    stage: str | None = None  # None = aggregated across stages
    cost: int | None = None
    traits: frozenset[str] = frozenset()
    sample_size: int = 0
    source: str = ""
    retrieved_at: str = ""


@dataclass(frozen=True)
class ItemStats:
    name: str
    average_placement: float = 0.0
    top4_rate: float = 0.0
    patch: str = ""
    win_rate: float = 0.0
    play_rate: float = 0.0
    holder: str | None = None  # None = aggregated across holders
    stage: str | None = None
    composition: str | None = None
    sample_size: int = 0
    source: str = ""
    retrieved_at: str = ""


@dataclass(frozen=True)
class TraitStats:
    name: str
    breakpoint: int | None = None  # active unit-count threshold; None = any
    stage: str | None = None
    average_placement: float = 4.5
    top4_rate: float = 0.0
    win_rate: float = 0.0
    play_rate: float = 0.0
    sample_size: int = 0
    patch: str = ""
    source: str = ""
    retrieved_at: str = ""


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """An atomic, validated bundle of normalized data for one patch.

    Ingestion builds a complete snapshot, validates it, then swaps it into the
    cache in one transaction — the live path never sees a partial import.
    """

    patch: str
    source: str
    retrieved_at: str
    # None = "this source does not provide the section; keep whatever the
    # active snapshot already has". [] = explicit empty (wipe the section).
    comps: list[CompStats] | None = None
    units: list[UnitStats] | None = None
    items: list[ItemStats] | None = None
    traits: list[TraitStats] | None = None


class StatsProvider(Protocol):
    def get_comps(self, patch: str) -> list[CompStats]: ...
    def get_unit(self, patch: str, name: str) -> UnitStats | None: ...
    def get_item(self, patch: str, name: str) -> ItemStats | None: ...
    def get_traits(self, patch: str) -> list[TraitStats]: ...


class InMemoryStatsProvider:
    """Development/test provider. Live play should read from a local cache."""

    def __init__(
        self,
        comps: list[CompStats],
        units: list[UnitStats] | None = None,
        items: list[ItemStats] | None = None,
        traits: list[TraitStats] | None = None,
    ) -> None:
        self._comps = list(comps)
        self._units = {item.name: item for item in (units or [])}
        self._items = {item.name: item for item in (items or [])}
        self._traits = list(traits or [])

    def get_comps(self, patch: str) -> list[CompStats]:
        return list(self._comps)

    def get_unit(self, patch: str, name: str) -> UnitStats | None:
        return self._units.get(name)

    def get_item(self, patch: str, name: str) -> ItemStats | None:
        return self._items.get(name)

    def get_traits(self, patch: str) -> list[TraitStats]:
        return list(self._traits)

    @classmethod
    def from_snapshot(cls, snapshot: KnowledgeSnapshot) -> "InMemoryStatsProvider":
        return cls(
            comps=snapshot.comps or [],
            units=snapshot.units or [],
            items=snapshot.items or [],
            traits=snapshot.traits or [],
        )
