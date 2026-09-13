from tft_engine import GameState, InMemoryStatsProvider, UnitState, evaluate_comps
from tft_engine.fixtures import FIXTURE_PATCH, build_fixture_snapshot
from tft_engine.sqlite_provider import SQLiteStatsProvider


def _provider() -> InMemoryStatsProvider:
    return InMemoryStatsProvider.from_snapshot(build_fixture_snapshot())


def _bruiser_leaning_state() -> GameState:
    return GameState(
        patch=FIXTURE_PATCH,
        stage="3-2",
        hp=55,
        gold=30,
        level=6,
        board=[UnitState("Vi", 2), UnitState("Warwick", 2), UnitState("Blitzcrank", 1)],
        bench=[UnitState("DrMundo", 1)],
        completed_items=["Bloodthirster"],
        contested_comps={"Bruiser Reroll": 0, "Arcane Burst": 3},
    )


def test_evaluate_comps_ranks_fitting_comp_first() -> None:
    ranked = evaluate_comps(_bruiser_leaning_state(), _provider(), top_n=4)
    assert ranked[0].name == "Bruiser Reroll"
    assert ranked[0].score > ranked[-1].score


def test_evaluation_exposes_contributions() -> None:
    ranked = evaluate_comps(_bruiser_leaning_state(), _provider(), top_n=1)
    top = ranked[0]
    names = {f.name for f in top.features}
    assert "core_unit_overlap" in names
    assert "contest" in names
    assert "sample_reliability" in names
    assert top.baseline != 0  # shrunk prior present
    assert top.score == top.baseline + top.context
    # Reasons exist for every non-zero contribution.
    assert top.reasons
    assert len(top.reasons) == sum(1 for f in top.features if f.contribution != 0)


def test_contest_pushes_comp_down() -> None:
    state = _bruiser_leaning_state()
    clean = evaluate_comps(state, _provider(), top_n=4)
    contested_state = _bruiser_leaning_state()
    contested_state.contested_comps["Bruiser Reroll"] = 3
    contested = evaluate_comps(contested_state, _provider(), top_n=4)
    before = next(e.score for e in clean if e.name == "Bruiser Reroll")
    after = next(e.score for e in contested if e.name == "Bruiser Reroll")
    assert after < before


def test_sqlite_provider_end_to_end(tmp_path) -> None:
    p = SQLiteStatsProvider(tmp_path / "k.db")
    p.apply_snapshot(build_fixture_snapshot())
    ranked = evaluate_comps(_bruiser_leaning_state(), p, top_n=2)
    assert ranked[0].name == "Bruiser Reroll"
    p.close()


def test_tiny_sample_comp_does_not_dominate() -> None:
    # Fixture "Lowcap Cheese" (avg 2.9, n=40) must not out-prior the
    # well-sampled field comps despite its extreme raw average.
    state = GameState(patch=FIXTURE_PATCH, stage="3-2", hp=50, gold=30, level=6)
    ranked = evaluate_comps(state, _provider(), top_n=4)
    baselines = {e.name: e.baseline for e in ranked}
    assert baselines["Lowcap Cheese"] < baselines["Arcane Burst"]
    assert baselines["Lowcap Cheese"] < baselines["Bruiser Reroll"]
