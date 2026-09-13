# Data Sources

Investigated 2026-09-13. Each source is rated on what it provides, how it is
accessed, update cadence, patch granularity, sample sizes, and access risk.
The project rule: **never build the pipeline around undocumented HTML or
gated internal endpoints when a stable sanctioned source exists.**

## Summary

| Source | Provides | Access | Verdict |
| --- | --- | --- | --- |
| Community Dragon | Set catalog: units (name, cost, traits), traits (breakpoints), items (recipes), augments | Public versioned JSON, no auth | **Selected — first adapter** |
| Riot Games API | Raw matches, league entries, summoner lookup | Free dev key, documented rate limits | Future `OwnDataAdapter` |
| MetaBot.GG MCP | Live comp stats: name, tier, win rate, pick rate, avg placement, unit lists | Public MCP endpoint, no auth, ~60 rpm | **Selected — stats adapter (implemented)** |
| TFTactics.gg | Comp tier + playstyle tag (Slow Roll(5)/Fast 8), unit rosters, **per-unit recommended items**; augment catalog w/ tier; roll-odds table; global item tier list | Server-rendered HTML, no auth | **Selected — structure adapter (implemented)** |
| LoLCHESS | `__NEXT_DATA__` JSON: current guide decks (boards w/ positions, stars, items, augments); meta stats with real sample sizes | Embedded JSON in page HTML | Partial — embedded stats verified **stale** (set 11 while live is set 18); guide decks current. Revisit as adapter if fresh stats reachable |
| MetaTFT | Aggregated comp stats (`comps_data`, `comps_stats`); augments w/ stats; early boards in-app | Endpoints exist but now gated/404; SPA shell only | Blocked — revisit with access |
| tactics.tools | Rich conditional stats (unit/item/holder); static set bundles at `ap.tft.tools/static/s{N}/data.js` | Undocumented internal API; static JS accessible | Not selected — API undiscovered, bundles usable as fallback catalog |
| Mobalytics | Tier lists, augment lists, per-comp guides | Bot-protected (403 to non-browser UA); data via internal XHR | Not selected — access unclear |

## Community Dragon (selected)

- **Endpoint:** `https://raw.communitydragon.org/latest/cdragon/tft/en_us.json`
  (also per-version paths like `.../15.x/cdragon/tft/en_us.json`)
- **Verified:** 2026-09-13, returns full JSON. Top-level keys: `items`,
  `setData`, `sets` (map of set number → `{champions, traits, name}`).
  Champions carry `apiName`, `name`, `cost`, `traits`, `role`, `stats`.
  Traits carry `apiName`, `name`, `effects[]` with `minUnits`/`maxUnits` —
  real breakpoints. Items carry `composition` (component recipes) and
  `isAugment` flags.
- **Fields:** catalog/statics only — no performance statistics.
- **Update cadence:** rebuilt on each game patch; `latest` tracks live.
- **Patch granularity:** versioned directories available.
- **Sample sizes:** n/a (statics).
- **Access/terms:** community-run mirror of game client data; the de-facto
  standard for TFT/LoL statics, used openly by many tools. No auth, no
  documented rate limits — still cache aggressively and fetch infrequently.
- **Role in this project:** normalization backbone — canonical unit/trait/
  item names, costs, and trait breakpoints per set. Performance priors come
  from a stats source layered on top.

## Riot Games API (future own-data pipeline)

- **Endpoint family:** `{platform}.api.riotgames.com/tft/...` — `tft-match-v1`
  (match list + match detail), `tft-league-v1`, `tft-summoner-v1`.
- **Fields:** full post-game states per participant: units, items, traits,
  level, placement, augments. Everything needed to compute *our own* priors.
- **Update cadence:** real-time.
- **Sample sizes:** we control them — bounded by rate limit (dev key ~100
  req/2min) and crawl seed size.
- **Access/terms:** documented ToS; requires a free developer key tied to a
  Riot account; keys expire and must not be committed.
- **Verdict:** the legitimate long-term stats source. Cost: a crawler +
  aggregation job. Defer until catalog + evaluation are solid.

## MetaBot.GG MCP (implemented — `ingest/metabot.py`)

- **Endpoint:** `https://metabot.gg/api/mcp` — streamable-HTTP MCP,
  `tools/call` → `get_team_comp` returns structuredContent with comp entries.
- **Verified:** 2026-09-13 — returns tier, win rate, pick rate, avg placement
  per comp; comp URLs encode unit apiNames, resolved to canonical names via
  the Community Dragon catalog.
- **Limitations:** ~8 comps per response (top meta only); **no per-comp
  sample sizes** — the adapter assigns a documented nominal N
  (`AGGREGATE_PSEUDO_N = 1000`) so shrinkage weights real data ~4:1 without
  treating N as exact. No per-unit/holder conditional stats.
- **Access/terms:** public, read-only, ~60 req/min/IP + global ceiling;
  attribution requested (comp URLs retained as `composition_id`).
- **Role:** live comp priors — the missing half Community Dragon can't
  provide.

## MetaTFT (blocked)

- **Historical endpoints (confirmed via Wayback):**
  `https://api2.metatft.com/tft-comps-api/comps_data?queue=1100`,
  `.../comps_stats?queue=1100&patch=current&days=2&rank=...&cluster_id=...`
- **Verified:** 2026-09-13 — all return 404/403 now; data appears moved
  behind a permit/auth mechanism. Their product aggregates ~2M games/day
  with per-rank/per-patch filtering — exactly the conditional stats this
  project wants.
- **Verdict:** highest-value stats source *if* access is granted. Do not
  scrape the site frontend. Revisit via their official channels.

## TFTactics.gg (implemented — `ingest/tftactics.py`)

- **Endpoint:** `https://tftactics.gg/tierlist/team-comps/` — server-rendered
  HTML; each `team-portrait` card carries rank (S/A/B/C), comp name, a
  playstyle tag (`Slow Roll (5)`, `Fast 8`, `Fast 9`, `Standard`,
  `Augment`, `Emblem`), unit roster, and **per-unit recommended items**.
- **Verified:** 2026-09-13 — 6 comp cards parsed live; additional tabs
  confirmed: `/tierlist/augments/` + `/db/augments/` (augment catalog with
  Silver/Gold/Prismatic tiers), `/tierlist/items/` (S/A/B item tier list),
  `/db/rolling/` (level-by-level shop odds table).
- **Limitations:** no performance statistics on the tier page — provides
  structure only (roster, item priorities, level plan via playstyle tag);
  HTML structure is unofficial and may drift. Requires a non-strict TLS
  context (Netlify "Root YE" cross-sign breaks OpenSSL strict mode; chain
  still signature-verified).
- **Role:** enriches MetaBot stats with `rank_bucket`, `typical_level`,
  `preferred_items` via `merge_comp_sources` (roster overlap >= 50%);
  unmatched TFTactics comps enter at neutral prior (n=0 → shrunk).

## LoLCHESS / MetaTFT / Mobalytics (not selected)

- **LoLCHESS** (`lolchess.gg/meta`) embeds `__NEXT_DATA__` JSON: current
  set-18 guide decks (full boards: positions, stars, per-unit items,
  augment picks) and `metaDeckExaltedStats` with **real sample sizes**
  (plays/wins/tops/avgPlacement/pickRate). Verified 2026-09-13: the
  embedded stats payload is **stale** (patch 14.14, set 11) — usable only
  if a fresh-stats route is found; guide decks remain current and could
  supply augment_preferences/item data later.
- **MetaTFT**: `/comps` + `/augments` are JS-only SPA shells (4KB, no data);
  historical `api2.metatft.com/tft-comps-api/*` endpoints return 404.
- **Mobalytics**: 403 to non-browser user agents; data loads via internal
  XHR — no stable ingestion surface.

## Decision

Three adapters, one pipeline (`--source full`):

1. **Community Dragon** — unit/trait/item catalog per set (statics).
2. **MetaBot.GG MCP + TFTactics.gg** — comps merged in one snapshot:
   MetaBot supplies performance stats (win/pick rates, avg placement);
   TFTactics supplies tier, tempo/level tag, and per-unit item priorities.

Next sources by value: Riot match-v1 crawler (own data, real sample sizes,
conditional stats) → authorized MetaTFT access (rich per-rank breakdowns)
→ LoLCHESS fresh-stats route (if discovered).
