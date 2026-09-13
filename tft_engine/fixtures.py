"""Hand-built fixture snapshot used by tests, the evaluation harness, and the
sample CLI until a real ingestion adapter lands. Numbers are plausible, not
real meta data — they exist to exercise the pipeline end to end.
"""

from __future__ import annotations

from .stats import CompStats, ItemStats, KnowledgeSnapshot, TraitStats, UnitStats

FIXTURE_PATCH = "15.5"


def build_fixture_snapshot(patch: str = FIXTURE_PATCH) -> KnowledgeSnapshot:
    retrieved = "2026-09-13T00:00:00Z"
    src = "fixture"
    comps = [
        CompStats(
            name="Bruiser Reroll",
            composition_id="fixture-bruiser-reroll",
            average_placement=4.05,
            top4_rate=0.55,
            win_rate=0.14,
            play_rate=0.09,
            sample_size=48200,
            core_units=frozenset({"Vi", "Warwick", "Blitzcrank", "DrMundo"}),
            optional_units=frozenset({"Twitch", "Zyra"}),
            preferred_items=frozenset({"Bloodthirster", "TitansResolve"}),
            augment_preferences=frozenset({"BuiltDifferent"}),
            typical_level=6,
            patch=patch,
            source=src,
            retrieved_at=retrieved,
        ),
        CompStats(
            name="Sniper Flex",
            composition_id="fixture-sniper-flex",
            average_placement=4.30,
            top4_rate=0.50,
            win_rate=0.11,
            play_rate=0.07,
            sample_size=35100,
            core_units=frozenset({"Jhin", "Caitlyn", "Ashe", "Braum"}),
            optional_units=frozenset({"Leona"}),
            preferred_items=frozenset({"InfinityEdge", "LastWhisper"}),
            typical_level=8,
            patch=patch,
            source=src,
            retrieved_at=retrieved,
        ),
        CompStats(
            name="Arcane Burst",
            composition_id="fixture-arcane-burst",
            average_placement=3.85,
            top4_rate=0.59,
            win_rate=0.16,
            play_rate=0.11,
            sample_size=51700,
            core_units=frozenset({"Ahri", "Lux", "Veigar", "Swain"}),
            optional_units=frozenset({"Annie"}),
            preferred_items=frozenset({"JeweledGauntlet", "BlueBuff"}),
            typical_level=8,
            patch=patch,
            source=src,
            retrieved_at=retrieved,
        ),
        CompStats(
            name="Lowcap Cheese",
            composition_id="fixture-lowcap-cheese",
            average_placement=2.90,
            top4_rate=0.71,
            win_rate=0.24,
            play_rate=0.01,
            sample_size=240,  # tiny sample: shrinkage must prevent domination
            core_units=frozenset({"Teemo", "Shaco"}),
            preferred_items=frozenset({"Guinsoo"}),
            typical_level=5,
            patch=patch,
            source=src,
            retrieved_at=retrieved,
        ),
    ]
    units = [
        UnitStats(name=n, cost=c, traits=frozenset(t), average_placement=ap,
                  top4_rate=t4, win_rate=wr, play_rate=pr, sample_size=ss,
                  patch=patch, source=src, retrieved_at=retrieved)
        for n, c, t, ap, t4, wr, pr, ss in [
            ("Vi", 2, {"Bruiser"}, 4.4, 0.50, 0.11, 0.30, 120000),
            ("Warwick", 3, {"Bruiser", "Chemtech"}, 4.1, 0.54, 0.13, 0.22, 88000),
            ("Blitzcrank", 2, {"Bruiser"}, 4.5, 0.48, 0.10, 0.18, 64000),
            ("DrMundo", 4, {"Bruiser"}, 4.0, 0.56, 0.14, 0.15, 52000),
            ("Jhin", 4, {"Sniper"}, 4.2, 0.53, 0.12, 0.19, 70000),
            ("Caitlyn", 1, {"Sniper"}, 4.6, 0.44, 0.09, 0.35, 140000),
            ("Ashe", 3, {"Sniper"}, 4.3, 0.52, 0.12, 0.17, 61000),
            ("Braum", 2, {"Warden"}, 4.5, 0.47, 0.10, 0.25, 91000),
            ("Ahri", 4, {"Arcane"}, 3.9, 0.58, 0.15, 0.21, 80000),
            ("Lux", 3, {"Arcane"}, 4.2, 0.53, 0.12, 0.20, 73000),
            ("Veigar", 2, {"Arcane"}, 4.4, 0.49, 0.10, 0.24, 69000),
            ("Swain", 3, {"Arcane", "Warden"}, 4.3, 0.51, 0.11, 0.16, 58000),
            ("Teemo", 1, {"Trickster"}, 4.8, 0.38, 0.07, 0.28, 100000),
            ("Shaco", 2, {"Trickster"}, 4.7, 0.40, 0.08, 0.12, 44000),
        ]
    ]
    items = [
        ItemStats(name=n, average_placement=ap, top4_rate=t4, win_rate=wr,
                  play_rate=pr, sample_size=ss, patch=patch, source=src,
                  retrieved_at=retrieved)
        for n, ap, t4, wr, pr, ss in [
            ("Bloodthirster", 4.1, 0.55, 0.13, 0.12, 61000),
            ("TitansResolve", 4.2, 0.53, 0.12, 0.10, 48000),
            ("InfinityEdge", 4.2, 0.53, 0.13, 0.14, 75000),
            ("LastWhisper", 4.3, 0.51, 0.11, 0.11, 52000),
            ("JeweledGauntlet", 4.0, 0.57, 0.14, 0.13, 68000),
            ("BlueBuff", 4.1, 0.55, 0.13, 0.12, 60000),
            ("Guinsoo", 4.4, 0.49, 0.10, 0.15, 80000),
        ]
    ]
    traits = [
        TraitStats(name=n, breakpoint=bp, average_placement=ap, top4_rate=t4,
                   win_rate=wr, play_rate=pr, sample_size=ss, patch=patch,
                   source=src, retrieved_at=retrieved)
        for n, bp, ap, t4, wr, pr, ss in [
            ("Bruiser", 2, 4.5, 0.47, 0.10, 0.20, 90000),
            ("Bruiser", 4, 4.1, 0.55, 0.13, 0.12, 52000),
            ("Sniper", 2, 4.4, 0.50, 0.11, 0.14, 64000),
            ("Sniper", 4, 4.2, 0.53, 0.12, 0.08, 33000),
            ("Arcane", 4, 4.0, 0.57, 0.14, 0.10, 45000),
            ("Warden", 2, 4.5, 0.48, 0.10, 0.18, 70000),
            ("Trickster", 2, 4.9, 0.35, 0.06, 0.05, 21000),
        ]
    ]
    return KnowledgeSnapshot(
        patch=patch,
        source=src,
        retrieved_at=retrieved,
        comps=comps,
        units=units,
        items=items,
        traits=traits,
    )
