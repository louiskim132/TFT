"""Ingestion tests use a recorded payload — the suite never hits the network.
The live fetch path is exercised manually via `python -m tft_engine.ingest`."""

import json

import pytest

from tft_engine.fixtures import build_fixture_snapshot
from tft_engine.ingest import (
    CommunityDragonAdapter,
    run_ingestion,
    validate_snapshot,
)
from tft_engine.sqlite_provider import SQLiteStatsProvider
from tft_engine.stats import KnowledgeSnapshot

CDRAGON_SAMPLE = json.dumps(
    {
        "items": [
            {"name": "Bloodthirster", "composition": ["BFSword", "NegatronCloak"]},
            {"name": "SomeAugment", "isAugment": True, "composition": []},
        ],
        "sets": {
            "18": {
                "name": "Set 18",
                "champions": [
                    {"apiName": "TFT18_Ahri", "name": "Ahri", "cost": 4,
                     "traits": ["TFT18_Arcane"]},
                    {"apiName": "TFT_BlueGolem", "name": "Golem", "cost": 1,
                     "traits": []},
                ],
                "traits": [
                    {"apiName": "TFT18_Arcane", "name": "Arcane",
                     "effects": [{"minUnits": 2, "maxUnits": 3},
                                 {"minUnits": 4, "maxUnits": 99}]},
                    {"apiName": "TFT18_Bruiser", "name": "Bruiser",
                     "effects": [{"minUnits": 2, "maxUnits": 3}]},
                ],
            }
        },
    }
).encode()


class FakeAdapter:
    name = "fake"

    def __init__(self, payload: bytes | Exception):
        self.payload = payload

    def fetch(self) -> bytes:
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def parse(self, raw: bytes):
        return CommunityDragonAdapter(patch="18.1").parse(raw)


def test_cdragon_parse_produces_catalog() -> None:
    snap = CommunityDragonAdapter(patch="18.1").parse(CDRAGON_SAMPLE)
    assert snap.patch == "18.1"
    assert snap.comps is None  # catalog source does not own comp stats
    units = {u.name: u for u in snap.units}
    assert units["Ahri"].cost == 4
    assert units["Ahri"].traits == frozenset({"Arcane"})
    bps = {(t.name, t.breakpoint) for t in snap.traits}
    assert ("Arcane", 4) in bps and ("Bruiser", 2) in bps
    items = {i.name for i in snap.items}
    assert "Bloodthirster" in items and "SomeAugment" not in items


def test_ingestion_populates_db(tmp_path) -> None:
    p = SQLiteStatsProvider(tmp_path / "k.db")
    result = run_ingestion(FakeAdapter(CDRAGON_SAMPLE), p)
    assert result["counts"]["units"] == 2
    assert result["counts"]["traits"] == 3
    unit = p.get_unit("18.1", "Ahri")
    assert unit is not None and unit.cost == 4
    p.close()


def test_catalog_snapshot_preserves_existing_comp_stats(tmp_path) -> None:
    p = SQLiteStatsProvider(tmp_path / "k.db")
    p.apply_snapshot(build_fixture_snapshot(patch="18.1"))
    comps_before = {c.name for c in p.get_comps("18.1")}
    run_ingestion(FakeAdapter(CDRAGON_SAMPLE), p)
    comps_after = {c.name for c in p.get_comps("18.1")}
    assert comps_before == comps_after  # catalog ingest did not wipe stats
    assert p.get_unit("18.1", "Ahri") is not None
    p.close()


def test_failed_fetch_keeps_previous_snapshot(tmp_path) -> None:
    p = SQLiteStatsProvider(tmp_path / "k.db")
    p.apply_snapshot(build_fixture_snapshot(patch="18.1"))
    with pytest.raises(OSError):
        run_ingestion(FakeAdapter(OSError("network down")), p)
    assert len(p.get_comps("18.1")) == 4
    p.close()


def test_invalid_snapshot_rejected() -> None:
    bad = KnowledgeSnapshot(patch="", source="", retrieved_at="")
    assert validate_snapshot(bad)


def test_malformed_payload_raises() -> None:
    adapter = CommunityDragonAdapter(patch="18.1")
    with pytest.raises(Exception):
        adapter.parse(b"not json")
