# Roadmap

The north star: given a correct GameState, return the 3 best actions from
current-patch statistical priors + contextual adjustment in <500ms.

## Done (work orders C1–C10)

- [x] C1 repo audit + packaging fix (hatchling wheel target)
- [x] C2 GameState schema v1: positions, traits, streak, opponents w/
      staleness, history, state_confidence; versioned JSON round-trip
- [x] C3 normalized knowledge schema: provenance + sample_size everywhere;
      Comp/Unit/Item/Trait records; KnowledgeSnapshot
- [x] C4 SQLiteStatsProvider: versioned schema, atomic snapshot swap,
      <50ms lookups (measured ~1ms)
- [x] C5 shrinkage toward lobby constants (k=250); tiny-sample trap test
- [x] C6 data-source investigation → docs/DATA_SOURCES.md
- [x] C7 Community Dragon adapter + ingestion pipeline; live snapshot
      verified (set 18: 91 units, 292 items, 90 trait breakpoints)
- [x] C8 CompEvaluator: explainable comp ranking over cached data;
      single implementation shared with live PLAY_COMP scoring
- [x] C9 evaluation harness: 10 scenarios, top1/top3/catastrophic/latency
- [x] C10 stdlib HTTP API: POST /decision, /health, /knowledge/status

## Next (rough priority)

1. ~~Real stats adapter~~ **Done** — MetaBot.GG MCP feeds live comp priors
   (win/pick rates, avg placement, unit rosters). Remaining gap: only ~8
   top-meta comps per pull and no upstream sample sizes (nominal N=1000).
   Deeper coverage needs Riot match-v1 own-data or authorized MetaTFT.
2. **Confidence model (Phase 9).** Replace sigmoid(|score|) with margin- +
   reliability-aware confidence; this is the gate for Tier-2 search.
3. **Action coverage.** SELL, LEVEL/PRELEVEL, SLAM, MOVE_ITEM candidates;
   item slam scoring (Phase 13); leveling model (Phase 11/15).
4. **Roll probability model (Phase 12).** Exact shop odds by level/cost +
   pool depletion → `roll_efficiency` feature.
5. **Decision logging (Phase 17).** Persist every decision + outcome join;
   the dataset that eventually replaces hand weights.
6. **Sealed holdout + shadow capture** for the eval harness.
7. **Board-strength model (Phase 21)** — first candidate for learned scoring
   once logging exists; only if eval shows handcrafted features failing.

## Explicitly deferred

CV/screen capture, overlay UI, input automation, combat sim, RL, neural
scoring, positioning search — per the plan's "excellent decision engine
first" ordering.
