import json

import pytest

from tft_engine.ingest.metabot import AGGREGATE_PSEUDO_N, MetaBotAdapter
from tft_engine.stats import UnitStats

METABOT_SAMPLE = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "structuredContent": {
                "patch": "16.18",
                "entries": [
                    {
                        "name": "Elder Dragon / Gnar comp",
                        "tier": "S",
                        "stats": [
                            {"label": "Win rate", "value": "87.2%"},
                            {"label": "Pick rate", "value": "0.7%"},
                            {"label": "Avg place", "value": "2.48"},
                        ],
                        "url": "https://metabot.gg/en/TFT/comp/"
                        "DA_18_ElderDragon-DA_18_GnarSmall-DA_18_Sentry-"
                        "DA_KogMaw18_AD/overview",
                    },
                    {
                        "name": "Ashe / Sivir comp",
                        "tier": "B",
                        "stats": [
                            {"label": "Win rate", "value": "80.2%"},
                            {"label": "Pick rate", "value": "0.3%"},
                            {"label": "Avg place", "value": "3.12"},
                        ],
                        "url": "https://metabot.gg/en/TFT/comp/"
                        "DA_18_Ashe-DA_18_Sivir/overview",
                    },
                ],
            }
        },
    }
).encode()


def _catalog() -> list[UnitStats]:
    return [
        UnitStats(name="Elder Dragon"),
        UnitStats(name="Gnar"),
        UnitStats(name="Sentry"),
        UnitStats(name="Ashe"),
        UnitStats(name="Sivir"),
        UnitStats(name="Kog'Maw"),
    ]


def test_metabot_parse_produces_comp_stats() -> None:
    adapter = MetaBotAdapter(patch="18.1", catalog_units=_catalog())
    snap = adapter.parse(METABOT_SAMPLE)
    assert snap.comps is not None and len(snap.comps) == 2
    assert snap.units is None and snap.traits is None  # doesn't own catalog
    top = snap.comps[0]
    assert top.name == "Elder Dragon / Gnar comp"
    assert top.average_placement == 2.48
    assert top.win_rate == 0.872
    assert top.play_rate == pytest.approx(0.007)
    assert top.sample_size == AGGREGATE_PSEUDO_N
    assert top.rank_bucket == "S"


def test_unit_names_resolved_via_catalog() -> None:
    adapter = MetaBotAdapter(patch="18.1", catalog_units=_catalog())
    snap = adapter.parse(METABOT_SAMPLE)
    top = snap.comps[0]
    # DA_18_ElderDragon -> "Elder Dragon", DA_18_GnarSmall -> "Gnar Small"->~"Gnar"
    assert "Elder Dragon" in top.core_units
    assert "Sentry" in top.core_units
    # Embedded set-number + stance suffix resolve to the catalog name.
    assert "Kog'Maw" in top.core_units


def test_empty_entries_rejected() -> None:
    adapter = MetaBotAdapter(patch="18.1")
    bad = json.dumps({"result": {"structuredContent": {"entries": []}}}).encode()
    with pytest.raises(ValueError):
        adapter.parse(bad)
