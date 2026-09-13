# TFT Decision Engine

A fast, provider-agnostic Teamfight Tactics decision engine designed for live recommendations under a 10-second decision budget.

## Current MVP

The live path is intentionally small and network-free:

1. Parse a canonical `GameState`.
2. Read already-cached statistical priors through `StatsProvider`.
3. Generate only relevant candidate actions.
4. Score each action with explicit named features.
5. Return ranked actions, reasons, confidence proxy, and measured latency.

The engine does **not** yet perform computer vision, mouse/keyboard automation, web scraping, or long-horizon combat simulation.

## Architecture

```text
MetaTFT / Mobalytics / Riot / own data
                |
        offline ingestion
                |
          local cache / DB
                |
           StatsProvider
                |
             GameState
                |
      Candidate Generator
                |
      Contextual Scoring
                |
        DecisionEngine
                |
 top actions + score + reasons
```

The internet should stay out of the live critical path. Meta/stat data should be refreshed separately and served from local storage during play.

## Why named score features?

Each score contribution is represented explicitly (for example `unit_overlap`, `item_fit`, `contest`, `hp_urgency`, and `econ_cost`). This makes recommendations inspectable now and gives us a clean training table later so hand-written weights can be replaced with learned/calibrated weights from actual outcomes.

## Run the sample

Python 3.11+:

```bash
python main.py
```

## Run tests

```bash
python -m pip install -e '.[dev]'
pytest
```

## JSON adapter

`tft_engine.json_api.decision_to_dict()` provides the initial boundary for a future HTTP/plugin endpoint. A future service can accept a JSON game state, construct `GameState`, call `DecisionEngine`, and return the serialized decision result without changing core decision logic.

## Next milestones

1. Add SQLite-backed cached statistics and normalized source schemas.
2. Implement ingestion adapters for approved/available TFT data sources.
3. Expand candidate generation for leveling, item slams, board swaps, and partial rolldowns.
4. Add stage/level/shop-odds aware upgrade probability.
5. Add lobby/scouting features and opponent pressure.
6. Calibrate action confidence from observed decision regret/outcomes.
7. Expose the engine as a small hosted API suitable for a ChatGPT plugin/action.
8. Only then add screen-state extraction; direct game input automation remains separate.

## Design constraint

The decision engine should normally finish far below the 10-second user decision window. Expensive search, if added later, should run only for ambiguous decisions and should have a hard time budget.
