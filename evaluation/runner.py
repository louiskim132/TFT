"""Deterministic evaluation harness.

Scenario fixtures (JSON) describe a GameState plus expected/unacceptable top
actions. The runner executes the engine over every scenario and reports
top-1/top-3 agreement, catastrophic picks, and latency — the metrics the
scoring system is tuned against.

    python -m evaluation.runner                 # fixture provider
    python -m evaluation.runner --db data/tft.db --patch 18.1

Scenario format:
    {
      "name": "...", "category": "econ|shop|comp|...",
      "importance": "low|normal|high",
      "state": { ...GameState payload... },
      "expected":     [{"type": "roll", "target_gold": 20}, ...],
      "unacceptable": [{"type": "hold"}, ...],
      "notes": "..."
    }
An action matches a spec when the action type and every specified field equal.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tft_engine import (
    CompStats,
    DecisionEngine,
    GameState,
    InMemoryStatsProvider,
    game_state_from_dict,
)
from tft_engine.fixtures import build_fixture_snapshot
from tft_engine.sqlite_provider import SQLiteStatsProvider

SCENARIO_DIR = Path(__file__).parent / "scenarios"


@dataclass(frozen=True)
class ActionSpec:
    type: str
    target: str | None = None
    target_gold: int | None = None

    def matches(self, action) -> bool:
        if action.action_type.value != self.type:
            return False
        if self.target is not None and action.target != self.target:
            return False
        if self.target_gold is not None and action.target_gold != self.target_gold:
            return False
        return True


@dataclass
class Scenario:
    name: str
    category: str
    state: GameState
    expected: list[ActionSpec]
    unacceptable: list[ActionSpec]
    importance: str = "normal"
    notes: str = ""


@dataclass
class ScenarioResult:
    name: str
    category: str
    top_action: str
    top3: list[str]
    top1_hit: bool
    top3_hit: bool
    catastrophic: bool
    latency_ms: float


@dataclass
class Report:
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def top1_rate(self) -> float:
        return _rate(r.top1_hit for r in self.results)

    @property
    def top3_rate(self) -> float:
        return _rate(r.top3_hit for r in self.results)

    @property
    def catastrophic_count(self) -> int:
        return sum(1 for r in self.results if r.catastrophic)

    @property
    def mean_latency_ms(self) -> float:
        return sum(r.latency_ms for r in self.results) / max(1, len(self.results))

    @property
    def max_latency_ms(self) -> float:
        return max((r.latency_ms for r in self.results), default=0.0)


def _rate(hits) -> float:
    hits = list(hits)
    return sum(hits) / len(hits) if hits else 0.0


def _spec(raw: dict) -> ActionSpec:
    return ActionSpec(
        type=str(raw["type"]),
        target=raw.get("target"),
        target_gold=raw.get("target_gold"),
    )


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    scenarios = []
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        scenarios.append(
            Scenario(
                name=raw.get("name", path.stem),
                category=raw.get("category", "general"),
                state=game_state_from_dict(raw["state"]),
                expected=[_spec(s) for s in raw.get("expected", [])],
                unacceptable=[_spec(s) for s in raw.get("unacceptable", [])],
                importance=raw.get("importance", "normal"),
                notes=raw.get("notes", ""),
            )
        )
    return scenarios


def _label(action) -> str:
    label = action.action_type.value
    if action.target:
        label += f"->{action.target}"
    if action.target_gold is not None:
        label += f" to {action.target_gold}g"
    return label


def run_scenario(engine: DecisionEngine, scenario: Scenario) -> ScenarioResult:
    result = engine.decide(scenario.state)
    top = result.actions[0] if result.actions else None
    top3 = result.actions[:3]
    return ScenarioResult(
        name=scenario.name,
        category=scenario.category,
        top_action=_label(top.action) if top else "<none>",
        top3=[_label(a.action) for a in top3],
        top1_hit=bool(top and any(s.matches(top.action) for s in scenario.expected)),
        top3_hit=any(
            s.matches(a.action) for a in top3 for s in scenario.expected
        ),
        catastrophic=bool(
            top and any(s.matches(top.action) for s in scenario.unacceptable)
        ),
        latency_ms=result.latency_ms,
    )


def evaluate(engine: DecisionEngine, scenarios: list[Scenario]) -> Report:
    return Report(results=[run_scenario(engine, s) for s in scenarios])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="evaluation.runner")
    ap.add_argument("--db", default=None, help="sqlite knowledge db path")
    ap.add_argument("--patch", default=None, help="override scenario patches")
    args = ap.parse_args(argv)

    provider_cm = None
    if args.db:
        provider_cm = SQLiteStatsProvider(args.db)
        provider = provider_cm
    else:
        provider = InMemoryStatsProvider.from_snapshot(build_fixture_snapshot())

    engine = DecisionEngine(provider, max_results=10)
    scenarios = load_scenarios()
    if args.patch:
        for s in scenarios:
            s.state.patch = args.patch
    report = evaluate(engine, scenarios)

    for r in report.results:
        flag = "CATASTROPHIC" if r.catastrophic else ("OK " if r.top1_hit else ("top3" if r.top3_hit else "MISS"))
        print(f"[{flag:12}] {r.name:42} top={r.top_action:28} ({r.latency_ms:.1f}ms)")
    print()
    print(f"top1: {report.top1_rate:.0%}   top3: {report.top3_rate:.0%}   "
          f"catastrophic: {report.catastrophic_count}   "
          f"latency mean {report.mean_latency_ms:.1f}ms / max {report.max_latency_ms:.1f}ms")

    if provider_cm:
        provider_cm.close()
    return 1 if report.catastrophic_count else 0


if __name__ == "__main__":
    sys.exit(main())
