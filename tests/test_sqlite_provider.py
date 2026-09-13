from time import perf_counter

from tft_engine.fixtures import FIXTURE_PATCH, build_fixture_snapshot
from tft_engine.sqlite_provider import SQLiteStatsProvider


def provider(tmp_path) -> SQLiteStatsProvider:
    p = SQLiteStatsProvider(tmp_path / "knowledge.db")
    p.apply_snapshot(build_fixture_snapshot())
    return p


def test_snapshot_round_trip(tmp_path) -> None:
    p = provider(tmp_path)
    comps = p.get_comps(FIXTURE_PATCH)
    assert len(comps) == 4
    by_name = {c.name: c for c in comps}
    bruiser = by_name["Bruiser Reroll"]
    assert bruiser.core_units == frozenset({"Vi", "Warwick", "Blitzcrank", "DrMundo"})
    assert bruiser.optional_units == frozenset({"Twitch", "Zyra"})
    assert bruiser.preferred_items == frozenset({"Bloodthirster", "TitansResolve"})
    assert bruiser.augment_preferences == frozenset({"BuiltDifferent"})
    assert bruiser.sample_size == 48200
    assert bruiser.source == "fixture"
    assert bruiser.typical_level == 6
    p.close()


def test_unknown_patch_returns_empty(tmp_path) -> None:
    p = provider(tmp_path)
    assert p.get_comps("0.0") == []
    assert p.get_unit("0.0", "Vi") is None
    p.close()


def test_unit_and_item_lookup(tmp_path) -> None:
    p = provider(tmp_path)
    unit = p.get_unit(FIXTURE_PATCH, "Warwick")
    assert unit is not None
    assert unit.cost == 3
    assert unit.traits == frozenset({"Bruiser", "Chemtech"})
    item = p.get_item(FIXTURE_PATCH, "JeweledGauntlet")
    assert item is not None and item.sample_size == 68000
    assert p.get_item(FIXTURE_PATCH, "Nonexistent") is None
    p.close()


def test_trait_lookup(tmp_path) -> None:
    p = provider(tmp_path)
    traits = p.get_traits(FIXTURE_PATCH)
    assert len(traits) == 7
    bps = {(t.name, t.breakpoint) for t in traits}
    assert ("Bruiser", 4) in bps
    p.close()


def test_atomic_snapshot_swap_keeps_previous_until_complete(tmp_path) -> None:
    p = provider(tmp_path)
    first = p.get_comps(FIXTURE_PATCH)
    # A second snapshot replaces the first only after full insert.
    snap2 = build_fixture_snapshot()
    snap2.comps[0] = type(snap2.comps[0])(
        **{**snap2.comps[0].__dict__, "average_placement": 3.5}
    )
    p.apply_snapshot(snap2)
    second = {c.name: c for c in p.get_comps(FIXTURE_PATCH)}
    assert second["Bruiser Reroll"].average_placement == 3.5
    # Old snapshot retained but inactive.
    status = p.knowledge_status()
    assert len(status["snapshots"]) == 2
    actives = [s for s in status["snapshots"] if s["active"]]
    assert len(actives) == 1 and actives[0]["id"] == 2
    p.close()


def test_lookup_latency_under_50ms(tmp_path) -> None:
    p = provider(tmp_path)
    p.get_comps(FIXTURE_PATCH)  # warm
    start = perf_counter()
    for _ in range(20):
        p.get_comps(FIXTURE_PATCH)
        p.get_unit(FIXTURE_PATCH, "Ahri")
        p.get_item(FIXTURE_PATCH, "BlueBuff")
        p.get_traits(FIXTURE_PATCH)
    elapsed_ms = (perf_counter() - start) * 1000 / 20
    assert elapsed_ms < 50
    p.close()


def test_knowledge_status_reports_counts(tmp_path) -> None:
    p = provider(tmp_path)
    status = p.knowledge_status()
    snap = status["snapshots"][0]
    assert snap["compositions"] == 4
    assert snap["unit_stats"] == 14
    assert snap["item_stats"] == 7
    assert snap["trait_stats"] == 7
    p.close()
