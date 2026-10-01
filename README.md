# TFT Decision Engine

A fast, provider-agnostic Teamfight Tactics decision engine designed for live recommendations under a 10-second decision budget.

## Current MVP

The live path is intentionally small and network-free:

1. Parse a canonical `GameState`.
2. Read already-cached statistical priors through `StatsProvider`.
3. Generate only relevant candidate actions.
4. Score each action with explicit named features.
5. Return ranked actions, reasons, confidence proxy, and measured latency.

The decision engine itself stays network- and I/O-free. Screen-state extraction lives in `tft_engine/capture/` (shop-card detection done; HUD, items, units in progress). Mouse/keyboard automation and combat simulation are out of scope.

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

## Current state (rev. 2026-10-01)

The project is **perception-first**: the engine core is built, and current
work is turning screenshots into `GameState` fields with confidence.

- **Shop-card detection** — all 65 set-18 units calibrated
  (`data/card_templates/18/`, Korean client). Binarized name strips,
  per-slot white-text windows, variant templates + blurred shift-tolerant
  matching. 220/220 slots correct on the calibration corpus (in-sample;
  held-out measurement lives in `tests/frames/`).
- **Held-out frames** — `tests/frames/`: 41 labeled shop bars (shop, level,
  XP, gold, streak per frame). Do not tune matchers against them.
- **Board units** — `data/board_templates/18/`: 14/65 3D model crops;
  matcher not built yet (S3, highest risk).
- **Schema v1** `GameState` with positions, traits, opponents (staleness-aware),
  history, and `state_confidence`; versioned JSON round-trip.
- **Knowledge cache** — `SQLiteStatsProvider` with atomic per-patch snapshots;
  `CommunityDragonAdapter` ingests the live unit/trait/item catalog
  (`python -m tft_engine.ingest --source cdragon --patch 18.1`).
- **Scoring** — shrunk meta priors (sample-size aware) + explicit named
  features; comps evaluated by the shared `CompEvaluator`.
- **Evaluation** — `python -m evaluation.runner` (10 scenarios; top-1/top-3/
  catastrophic/latency).
- **API** — `python -m tft_engine.api [--db data/tft.db]` serves
  `POST /decision`, `GET /health`, `GET /knowledge/status`.

Docs: `docs/ARCHITECTURE.md`, `docs/DATA_SOURCES.md`, `docs/SCORING.md`,
`docs/EVALUATION.md`, `docs/ROADMAP.md`.

## Next milestones

See `docs/ROADMAP.md` (dated sprint plan) and the latest audit in
`docs/AUDIT_2026-10-01.md`.

## Design constraint

The decision engine should normally finish far below the 10-second user decision window. Expensive search, if added later, should run only for ambiguous decisions and should have a hard time budget.
