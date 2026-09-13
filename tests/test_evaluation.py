from tft_engine import DecisionEngine, InMemoryStatsProvider
from tft_engine.fixtures import build_fixture_snapshot

from evaluation.runner import evaluate, load_scenarios


def _report():
    provider = InMemoryStatsProvider.from_snapshot(build_fixture_snapshot())
    engine = DecisionEngine(provider, max_results=10)
    return evaluate(engine, load_scenarios())


def test_scenarios_load() -> None:
    scenarios = load_scenarios()
    assert len(scenarios) >= 10
    assert all(s.state.patch for s in scenarios)


def test_harness_metrics() -> None:
    report = _report()
    assert report.top3_rate >= 0.9
    assert report.catastrophic_count == 0
    assert report.mean_latency_ms < 500  # far under the 10s decision budget


def test_critical_hp_regression() -> None:
    # Permanent guard: at critical HP the engine must never top-rank HOLD.
    report = _report()
    result = next(r for r in report.results if r.name == "critical_hp_should_stabilize")
    assert not result.catastrophic
    assert result.top_action != "hold"
