"""Ingestion pipeline: fetch -> parse -> validate -> atomic snapshot swap.

If any step fails, the previously active snapshot stays in place.
"""

from __future__ import annotations

from ..sqlite_provider import SQLiteStatsProvider
from .base import SourceAdapter, validate_snapshot


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
