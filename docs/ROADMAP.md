# Roadmap

**North star:** from the live game screen, produce a correct `GameState`
and return the 3 highest-win-rate moves within 1 s of a state change, with
an explanation for each.

Current audit: [`AUDIT_2026-10-01.md`](AUDIT_2026-10-01.md) (~35% toward
the north star).

## Tracks

| Track | Goal | Owner modules |
| --- | --- | --- |
| **P — Perception** | screen → per-field values + confidence | `tft_engine/capture/` |
| **K — Knowledge** | fresh comps, level plans, items, augments | `tft_engine/ingest/`, `sqlite_provider.py` |
| **D — Decision** | full action coverage + calibrated confidence | `candidates.py`, `scoring.py`, `engine.py` |
| **I — Integration** | capture loop → engine → on-screen output | new `tft_engine/live/` |
| **Q — Quality** | CI, labeled frames, eval scenarios, logging | `tests/`, `evaluation/` |

## Done (through 2026-09-16)

- [x] C1–C10: packaging, GameState schema v1, normalized knowledge schema,
      SQLite provider, shrinkage, data-source study, cdragon ingest,
      CompEvaluator, eval harness (10 scenarios), HTTP API
- [x] MetaBot.GG comp priors + TFTactics rosters/items, merged
- [x] CHOOSE_AUGMENT need-based selection
- [x] Shop-card detection: 65 set-18 units, Korean client, variant and
      blur-shift tolerant (in-sample only)

## Revision plan (rev. 2026-10-01)

Two-week sprints. Each sprint ends with a dated audit that updates this
file. Exit criteria are measured, not judged.

### S0 · Stabilize — Oct 1 – Oct 4

- [x] Q: declare `numpy`, `Pillow` deps; push `main`; CI green —
      10-01: pushed `27df741`, CI run 36866674478 green (prior run
      failed on undeclared deps as predicted)
- [x] Q: commit board-template manifest, gitignore its PNGs (10-01:
      14/65 model crops stored, manifest committed)
- [x] Q: label 30 held-out frames (`tests/frames/`, JSON sidecar per
      frame with every visible field). **No CV tuning on these.** —
      done 10-01: 41 bars labeled (shop, level, xp, gold, streak);
      shop labels are calibration-derived (flagged in sidecars)
- [x] K: refresh `data/tft.db` (`--source full`) — done 10-01:
      snapshot 10, cdragon 91u/292i/90t + metabot+tftactics 12 comps
- [x] Docs: README "current state" now says the project is perception-first

**Exit:** CI green on `origin/main`; held-out frame set exists.

### S1 · HUD extraction + fresh knowledge — Oct 5 – Oct 16

- [ ] P: digit/glyph templates (same binarize + bbox method as shop strips)
- [ ] P: from the shop bar: **gold, level, XP x/y, streak, shop odds**
      (odds act as a level cross-check)
- [ ] P: full-frame ROIs: **stage/round, own HP**
- [ ] P: each field returns `(value, confidence)`
- [ ] K: staleness guard. `/knowledge/status` reports age, and the engine
      flags its output when the snapshot is more than 3 days old
- [ ] K: scheduled refresh (daily) + LoLCHESS guide decks for level
      timings, augments and items (fills `composition_augments`)

**Exit:** ≥98% exact-match on HUD fields over the held-out frames; DB age
under 24 h.
**Audit:** 2026-10-16.

### S2 · Live loop + action coverage — Oct 19 – Oct 30

- [ ] I: window capture (`mss`) of the TFT client, resolution-normalized
      ROIs (1080p, 1440p, 4K)
- [ ] I: `StateAssembler`: per-frame fields → `GameState` with
      `state_confidence`; temporal smoothing across ~3 frames; change
      detection so decisions fire only on state change
- [ ] I: `python -m tft_engine.live` prints the top-3 in a terminal side
      window (no overlay yet)
- [ ] D: LEVEL / PRELEVEL candidates driven by the comp's level plan
- [ ] D: roll-odds model (ingest TFTactics roll table + pool depletion)
      → `roll_efficiency`
- [ ] D: SELL candidates (bench clutter, gold for a level breakpoint)

**Exit:** a real game runs end to end on HUD + shop fields; recommendation
latency under 1 s; eval top-3 ≥90% on the real DB.
**Audit:** 2026-10-30.

### S3 · Items, bench, board — Nov 2 – Nov 13

- [ ] P: item components + completed items (cdragon 2D icons; bench item
      row + unit hover)
- [ ] P: bench units + star level (star pips)
- [ ] P: board units, **highest risk**. Try the trait panel plus model-crop
      matching (`board_templates`); fallback is a one-click user
      confirmation of the board
- [ ] D: SLAM_ITEM candidates + item-fit scoring (TFTactics per-unit items)
- [ ] D: margin- and reliability-aware confidence (replaces the sigmoid)
- [ ] Q: decision logging (every state + top-3 + chosen action) to SQLite

**Exit:** items/bench ≥95%, board ≥90% (or the fallback is shipped);
every live decision is logged.
**Audit:** 2026-11-13.

### S4 · Opponents + MVP pilot — Nov 16 – Nov 27

- [ ] P: scoreboard → all 8 players' HP (+ names); opponent level and
      board captured opportunistically while scouting, staleness-stamped
- [ ] D: contest penalties from observed opponent boards (schema exists)
- [ ] I: decide the output surface after a **Riot policy check** (overlay
      vs second-screen web page served by `api.py`)
- [ ] Q: pilot of 10 real games with logging on

**Exit:** 10 logged games; per-field perception accuracy reported from
real games; no catastrophic recommendations in review.
**Audit:** 2026-11-27.

### S5 · Evaluate on real play — Nov 30 – Dec 11

- [ ] Q: turn logged states into eval scenarios (target: 50 dev + 20
      sealed holdout)
- [ ] Q: outcome join (placement per game) on the decision log
- [ ] K: scope the Riot `tft-match-v1` own-data crawler (real sample sizes)
- [ ] P: set-change drill: rebuild all templates in under 1 h from a
      script

**Exit:** eval runs on real-game scenarios with a sealed holdout; a
recalibration runbook exists.
**Audit:** 2026-12-11.

### Later (2026-12-14 →)

Learned/calibrated feature weights from the decision log; own-data stats
pipeline; positioning advice; Tier-2 search for low-confidence decisions.
Combat simulation and RL stay out until evaluation shows the handcrafted
baseline failing in ways they would fix.

## Out of scope (permanent)

Input automation (clicking or buying for the player), memory reading or
client injection, and scraping gated endpoints. Opponent XP is never shown
in the client, so only opponent level is tracked.

## Revision log

| Date | Change |
| --- | --- |
| 2026-09-13 | Original roadmap: engine-first, CV deferred (C1–C10 complete) |
| 2026-10-01 | Audit. The project already pivoted to perception (shop CV, 09-15/16) without a doc update. Roadmap rewritten around the 5 tracks with dated sprints S0–S5. New: held-out frame set, staleness guard, CI repair, live loop, Riot-policy gate before any overlay. Dropped: opponent XP (not observable). |
| 2026-10-01 | S0 round: 65-unit shop matcher finalized (variants + blur-shift, 220/220 in-sample, ~0.28 s/shop); 14 board-model crops stored under `data/board_templates/18/`; `tests/frames/` created — 41 labeled bars (shop/level/xp/gold/streak); `numpy`+`Pillow` declared; `tft.db` refreshed (snapshot 10); README updated. Pushed `27df741` — **CI green on origin/main; S0 exit met.** |
| 2026-10-01 | P (S3 early): 24 more board-unit model crops labeled by user → **38/65 board templates**. Name check: `독두꺼비` mapped to Gromp (only toad unit in catalog — possible namu vs in-game naming gap), `늑대`→Murk Wolf, `바위게`→Scuttlecrab. Board matcher itself still TBD (needs full board frames for hex-cell geometry). |
| 2026-10-01 | P (S3): +7 crops → **44/65 board units** (Pebbles, Morgana, Sentinel, Aphelios, Malphite, Soraka ×2). `독두꺼비` confirmed = Gromp alias. Missing: 3×c1 (Kobuko, Rek'Sai, Cinderling), 3×c2 (Alistar, Yunara, Sejuani), Master Yi, 4×c4 (Lillia, Sett, Amumu, Sivir), all 10 five-costs. |
| 2026-10-01 | P (S3): +11 crops → **55/65 board units** (Amumu, Alistar, Yunara, Master Yi, Sejuani, Sett, Gnar, Taric, Maokai, Sivir, Kennen). Noted: item icons render in a row under the health bar — exclude that band when matching models. `독두꺼비`→Gromp alias added to `kr_names.json`. Missing 10: Kobuko, Rek'Sai, Cinderling, Lillia, + 6 five-costs (Ashe, Elder Dragon, Ivern, Lux, Alune, Draven). |
