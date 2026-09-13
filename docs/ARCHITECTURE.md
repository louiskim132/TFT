# Architecture

## Boundaries (non-negotiable)

```
observation (manual / OCR / replay / other program)
        │
        ▼
   GameState                    <- canonical, versioned (state_io.py)
        │
        ▼
DecisionEngine                  <- never does I/O, never touches network
        │
        ▼
actions + scores + reasons + confidence
```

```
sources (CommunityDragon / MetaTFT / Riot / own data)
        │
        ▼
SourceAdapter.fetch/parse       <- network lives ONLY in tft_engine/ingest/
        │
        ▼
KnowledgeSnapshot               <- normalized, provider-neutral records
        │
        ▼
SQLiteStatsProvider             <- atomic snapshot swap per patch
        │
        ▼
   StatsProvider (protocol)     <- engine reads only through this
```

## Module map

| Module | Role |
| --- | --- |
| `models.py` | GameState, actions, score/result records. `SCHEMA_VERSION` |
| `state_io.py` | JSON (de)serialization, validation, version rejection |
| `stats.py` | Normalized stat records (`CompStats`, `UnitStats`, `ItemStats`, `TraitStats`), `KnowledgeSnapshot`, `StatsProvider` protocol, `InMemoryStatsProvider` |
| `sqlite_provider.py` | Persistent cache; `PRAGMA user_version` migrations; `apply_snapshot` is one transaction + active-flag flip; section inheritance (`None` = keep prior) |
| `reliability.py` | `shrunk_value` — sample-size shrinkage toward lobby constants |
| `candidates.py` | Strategically meaningful candidate generation only |
| `scoring.py` | `ActionScorer` — named feature vector per action |
| `comp_eval.py` | `CompEvaluator` — the single implementation behind comp scoring *and* the `evaluate_comps` diagnostic surface |
| `engine.py` | `DecisionEngine.decide` — comps → candidates → score → rank |
| `json_api.py` | function-level adapter (in-process JSON boundary) |
| `api.py` | stdlib HTTP service: `POST /decision`, `GET /health`, `GET /knowledge/status` |
| `ingest/` | `SourceAdapter` protocol, `cdragon.py`, `pipeline.py`, CLI |
| `fixtures.py` | hand-built snapshot for tests/eval until stats ingestion lands |
| `evaluation/` | scenario fixtures + runner (top1/top3/catastrophic/latency) |

## Data flow for a live decision

1. `game_state_from_dict` validates/normalizes the payload (schema v1).
2. `provider.get_comps(patch)` reads the active snapshot (<50ms, indexed).
3. `generate_candidates` emits ~5–30 actions (buy/roll/hold/play_comp).
4. `ActionScorer` produces `Score = baseline(prior) + Σ named features`.
5. Result carries actions, per-feature contributions, reasons, confidence,
   measured latency.

## Latency posture

Measured in the evaluation harness: ~0.2ms mean decision on the fixture
snapshot. DB lookups are single-digit ms. The 10s budget is almost entirely
reserved for future Tier-2 search — not needed yet.

## What is deliberately absent

No combat simulator, no RL, no CV, no input automation, no RL/NN scoring.
Per the plan these arrive only when the evaluation harness demonstrates the
handcrafted baseline failing in ways they would fix.
