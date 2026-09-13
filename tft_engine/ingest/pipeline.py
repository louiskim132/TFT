"""Ingestion pipeline: fetch -> parse -> validate -> atomic snapshot swap.

If any step fails, the previously active snapshot stays in place.
"""

from __future__ import annotations

from dataclasses import replace

from ..sqlite_provider import SQLiteStatsProvider
from ..stats import CompStats
from .base import SourceAdapter, validate_snapshot

_MERGE_MIN_OVERLAP = 0.5


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def merge_comp_sources(
    primary: list[CompStats], enrich: list[CompStats]
) -> list[CompStats]:
    """Combine a stats-bearing comp list with a structure-bearing one.

    Each `primary` comp keeps its performance stats; a matching `enrich` comp
    (roster overlap >= 50%) contributes name, rank_bucket, typical_level,
    preferred_items, and any missing core units. Unmatched enrich comps are
    appended with their neutral priors so a broader tier list still reaches
    the engine even without performance data.
    """

    merged: list[CompStats] = []
    used: set[int] = set()
    for comp in primary:
        best_i, best_score = -1, 0.0
        for i, other in enumerate(enrich):
            if i in used:
                continue
            score = _overlap(comp.core_units, other.core_units)
            if score > best_score:
                best_i, best_score = i, score
        if best_i >= 0 and best_score >= _MERGE_MIN_OVERLAP:
            other = enrich[best_i]
            used.add(best_i)
            merged.append(
                replace(
                    comp,
                    name=other.name or comp.name,
                    rank_bucket=other.rank_bucket or comp.rank_bucket,
                    typical_level=other.typical_level or comp.typical_level,
                    preferred_items=other.preferred_items or comp.preferred_items,
                    core_units=comp.core_units | other.core_units,
                )
            )
        else:
            merged.append(comp)
    for i, other in enumerate(enrich):
        if i not in used:
            merged.append(other)
    return merged


def run_ingestion(adapter: SourceAdapter, provider: SQLiteStatsProvider) -> dict:
    raw = adapter.fetch()
    snapshot = adapter.parse(raw)
    issues = validate_snapshot(snapshot)
    if issues:
        raise ValueError(f"snapshot failed validation: {issues}")
    snapshot_id = provider.apply_snapshot(snapshot)
    return {
        "snapshot_id": snapshot_id,
        "patch": snapshot.patch,
        "source": snapshot.source,
        "retrieved_at": snapshot.retrieved_at,
        "counts": {
            "comps": None if snapshot.comps is None else len(snapshot.comps),
            "units": None if snapshot.units is None else len(snapshot.units),
            "items": None if snapshot.items is None else len(snapshot.items),
            "traits": None if snapshot.traits is None else len(snapshot.traits),
        },
    }
