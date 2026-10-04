# Roadmap

**North star:** from the live game screen, produce a correct `GameState`
and return the 3 highest-win-rate moves within 1 s of a state change, with
an explanation for each.

Current audit: [`AUDIT_2026-10-04.md`](AUDIT_2026-10-04.md) (~38% toward
the north star). Previous: [`AUDIT_2026-10-01.md`](AUDIT_2026-10-01.md).

## Working rules (added 2026-10-04)

1. **WIP limit.** Only work on items from the current sprint. Anything else
   is a *spike*: time-boxed to 1 day, announced in the log first, and
   closed with a go/no-go line.
2. **No unmeasured CV.** Every frame used to fit or tune a perception
   routine is saved under `tests/frames/` with a labeled sidecar *before*
   the change is committed. Holdout frames are never used for tuning.
3. **Canonical resolution.** Extractors run on frames resized to one
   working resolution. Thresholds are fractions or are defined at that
   resolution, never raw pixels of whatever was pasted.
4. **Log, not diary.** One revision-log row per session or sprint.

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

## Revision plan (rev. 2026-10-04)

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

### Spike · Board perception — Oct 1 – Oct 4 (unplanned, closed)

Pulled S3 forward with no time box. Outcome: **go** on the stats-panel
path, **no-go** on 3D model matching as the primary signal.

- [x] 3D model crop library, 65/65 units + 9 Lux variants
      (`data/board_templates/18/`). **Frozen**: fallback / tie-breaker
      only, and its KR trait→variant map feeds the trait reader
- [x] `capture/board.py` prototypes: health-bar anchors, stats-panel gate
      + portraits, star pips (1★ = no pips), trait rows, bench strip,
      on-model star aura
- [ ] **Debt:** the frames behind these prototypes were not saved, and the
      8 tests are synthetic. Paid off in S1 (frame corpus)

### S1 · Frame corpus, HUD extraction, fresh knowledge — Oct 5 – Oct 16

Order matters: the corpus and the benchmark come first, so every later
item has a measured result.

- [ ] K: **staleness guard (day 1).** `/knowledge/status` reports age, and
      the engine flags its output when the snapshot is more than 3 days old.
      The DB crosses that threshold on 10-04
- [ ] K: scheduled daily refresh (`--source full`)
- [ ] Q: **frame corpus.** `tests/frames/full/`, ≥30 *native-resolution*
      full frames with sidecars, covering planning, combat, stats panel
      open, scouting, augment pick, carousel and level 10. Re-capture the
      board-spike scenes. Split dev/holdout (≥10 holdout)
- [ ] Q: ≥20 **new** shop bars as the first true shop holdout (the current
      41 are the calibration set)
- [ ] Q: `python -m evaluation.perception` gives per-field exact-match over
      `tests/frames/` (dev and holdout reported separately) and runs in CI
- [ ] P: canonical-resolution normalizer (`capture/frame.py`). Every
      extractor takes a normalized frame. Convert `board.py` absolute-pixel
      gates (bar height, portrait side, pip run, merge slack)
- [ ] P: digit/glyph templates (same binarize + bbox method as shop strips)
- [ ] P: shop bar → **gold, level, XP x/y, streak, shop odds** (odds
      cross-check level)
- [ ] P: full-frame ROIs → **stage/round, own HP**
- [ ] P: trait panel → **trait name + count** via the same glyph matcher
      (KR trait map; also resolves the Lux variant)
- [ ] P: each field returns `(value, confidence)`

**Exit:** ≥98% exact-match on HUD fields (gold/level/XP/streak/stage/HP)
over the **holdout** frames; trait name+count ≥95% on dev; shop accuracy
reported on the new holdout; DB age under 24 h with the guard live.
**Audit:** 2026-10-16.

### S2 · Live loop + action coverage — Oct 19 – Oct 30

- [ ] I: window capture (`mss`) of the TFT client → normalizer from S1
      (1080p, 1440p, 4K verified on one frame each)
- [ ] I: `StateAssembler`: per-frame fields → `GameState` with
      `state_confidence`; temporal smoothing across ~3 frames; change
      detection so decisions fire only on state change
- [ ] I: `python -m tft_engine.live` prints the top-3 in a terminal side
      window (no overlay yet), and **saves every frame it decides on**, so
      the corpus grows for free
- [ ] D: LEVEL / PRELEVEL candidates driven by the comp's level plan
- [ ] D: roll-odds model (ingest TFTactics roll table + pool depletion)
      → `roll_efficiency`
- [ ] D: SELL candidates (bench clutter, gold for a level breakpoint)
- [ ] D: fix the real-DB eval miss (`contested_comp_penalized`)

**Exit:** a real game runs end to end on HUD + shop + trait fields;
recommendation latency under 1 s; eval top-3 ≥90% on the real DB.
**Audit:** 2026-10-30.

### S3 · Items, bench, board — Nov 2 – Nov 13

Re-scoped after the spike. The primary board signal is the **stats panel +
trait panel + health-bar count**, and model crops are fallback only.

- [ ] P: **confirm the bench.** Is the left-edge portrait column really the
      bench? If not, locate the bench row under the board. Decide on
      ≥5 corpus frames
- [ ] P: stats-panel portrait identity, calibrated from labeled panel
      frames (like the shop strips). One template set shared with the bench
      if the render family matches
- [ ] P: star pips measured on the corpus (opp-column clipping is the
      known failure mode); aura fallback for units without a panel row
- [ ] P: item components + completed items (cdragon 2D icons; bench item
      row + unit hover)
- [ ] P: board roster = panel identities ∪ trait-count consistency check;
      health-bar count is a sanity bound. Fallback is a one-click user
      confirmation of the board
- [ ] D: SLAM_ITEM candidates + item-fit scoring (TFTactics per-unit items)
- [ ] D: margin- and reliability-aware confidence (replaces the sigmoid)
- [ ] Q: decision logging (every state + top-3 + chosen action) to SQLite

**Exit:** items/bench ≥95%, board roster ≥90% on holdout (or the fallback
is shipped); every live decision is logged.
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
- [ ] P: set-change drill: rebuild all templates (shop strips, glyphs,
      panel portraits, trait names) in under 1 h from a script

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
| 2026-10-01 → 10-04 | **Unplanned S3 spike** (15 commits, see audit 10-04). Board model-crop library completed: 65/65 units + all 9 Lux variants (variant identified by the portrait/trait-panel trait line; no base Lux). KR alias gaps fixed: `독두꺼비`→Gromp, `불타는 정령`→Cinderling. Finding: 3D model matching is weak at 1024×575, so the library is frozen. `capture/board.py`: health-bar anchors, stats-panel portraits + pip detector (1★ shows no pips; own column read correctly on one frame, opp ~90%), trait rows, bench strip, star aura; RGBA alpha bug fixed. 74 tests, CI green. **Source frames were not saved.** |
| 2026-10-04 | Audit ([`AUDIT_2026-10-04.md`](AUDIT_2026-10-04.md)), ~38%. Added working rules (WIP limit, no unmeasured CV, canonical resolution, compact log). S1 now starts with the staleness guard, a native-resolution frame corpus, a new shop holdout and a perception benchmark; the resolution normalizer moves S2→S1; the trait-panel reader joins S1. S3 board re-scoped to stats panel + trait panel + health bars, with bench identity to confirm. S2 adds frame saving in the live loop and the real-DB eval fix. |
