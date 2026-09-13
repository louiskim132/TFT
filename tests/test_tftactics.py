"""TFTactics adapter tests with recorded HTML — no network."""

from __future__ import annotations

from tft_engine.ingest.pipeline import merge_comp_sources
from tft_engine.ingest.tftactics import TFTacticsAdapter
from tft_engine.stats import CompStats

_HTML = b"""
<html><body>
<div class="team-portrait"><div class="team-name">
<div class="team-rank tone">S</div>
<div class="team-name-elipsis">Blossom Spellweavers
<div class="team-name-extra"><div class="team-playstyle">Fast 8</div></div></div></div>
<div class="team-characters">
<a href="/champions/karma/" class="characters-item c1 s18"><div class="character-wrapper"><img alt="Karma" src="x.png"></div><div class="team-character-name">Karma</div></a>
<a href="/champions/ahri/" class="characters-item c4 s18"><div class="character-wrapper"><img alt="Ahri" src="x.png"></div>
<div class="character-items"><div class="characters-item"><div class="character-wrapper" name="Jeweled Gauntlet" type="Combined"><img alt="Jeweled Gauntlet" src="x.png"></div></div>
<div class="characters-item"><div class="character-wrapper" name="Spear of Shojin" type="Combined"><img alt="Spear of Shojin" src="x.png"></div></div></div>
<div class="team-character-name">Ahri</div></a>
</div></div>
<div class="team-portrait"><div class="team-name">
<div class="team-rank tone">A</div>
<div class="team-name-elipsis">Riftbeasts Reroll
<div class="team-name-extra"><div class="team-playstyle">Slow Roll (5)</div></div></div></div>
<div class="team-characters">
<a href="/champions/reksai/" class="characters-item c2 s18"><div class="character-wrapper"><img alt="Rek'Sai" src="x.png"></div><div class="team-character-name">Rek'Sai</div></a>
</div></div>
</body></html>
"""


def _comp(name, units, **kw):
    return CompStats(
        name=name,
        average_placement=kw.get("avg", 4.0),
        top4_rate=kw.get("top4", 0.5),
        win_rate=kw.get("wr", 0.1),
        play_rate=0.05,
        sample_size=kw.get("n", 500),
        core_units=frozenset(units),
        preferred_items=kw.get("preferred_items", frozenset()),
        patch="18.1",
        source="metabot_gg",
        retrieved_at="2026-05-24T00:00:00+00:00",
        **{k: v for k, v in kw.items() if k in ("rank_bucket", "typical_level")},
    )


def test_parse_extracts_tier_name_style_units_items():
    snap = TFTacticsAdapter(patch="18.1").parse(_HTML)
    assert len(snap.comps) == 2
    s, a = snap.comps
    assert s.name == "Blossom Spellweavers" and s.rank_bucket == "S"
    assert s.typical_level == 8
    assert s.core_units == frozenset({"Karma", "Ahri"})
    assert s.preferred_items == frozenset({"Jeweled Gauntlet", "Spear of Shojin"})
    assert a.typical_level == 5 and a.sample_size == 0


def test_parse_rejects_empty_payload():
    try:
        TFTacticsAdapter(patch="18.1").parse(b"<html>nothing</html>")
        assert False
    except ValueError:
        pass


def test_merge_enriches_matching_comp_and_keeps_stats():
    primary = [_comp("Elder Dragon / Gnar", {"Gnar", "Sett"}, avg=2.5, n=1000)]
    enrich = [
        _comp(
            "Apex Predator",
            {"Gnar", "Sett", "Nidalee"},
            n=0,
            rank_bucket="S",
            typical_level=8,
            preferred_items=frozenset({"Bloodthirster"}),
        )
    ]
    merged = merge_comp_sources(primary, enrich)
    assert len(merged) == 1
    m = merged[0]
    assert m.average_placement == 2.5 and m.sample_size == 1000  # stats kept
    assert m.name == "Apex Predator" and m.rank_bucket == "S"
    assert m.typical_level == 8 and "Bloodthirster" in m.preferred_items
    assert "Nidalee" in m.core_units  # union


def test_merge_appends_unmatched_enrich_comps():
    primary = [_comp("A", {"Gnar"}, n=100)]
    enrich = [_comp("B", {"Karma", "Ahri"}, n=0, rank_bucket="S")]
    merged = merge_comp_sources(primary, enrich)
    assert {c.name for c in merged} == {"A", "B"}
