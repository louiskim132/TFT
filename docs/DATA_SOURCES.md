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
| MetaTFT | Aggregated comp stats (`comps_data`, `comps_stats`) | Endpoints exist but now gated/404 without permit | Blocked — revisit with access |
| tactics.tools | Rich conditional stats (unit/item/holder) | Undocumented internal API | Not selected — access unclear |
| Mobalytics | Tier lists, guides | Undocumented | Not selected — access unclear |

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

## tactics.tools / Mobalytics (not selected)

Both serve excellent stats through undocumented internal APIs whose
stability and terms are unclear. Per the project rule above, they are not
foundations. Re-evaluate if either publishes a supported export.

## Decision

Two adapters, one pipeline (`--source full`):

1. **Community Dragon** — unit/trait/item catalog per set (statics).
2. **MetaBot.GG MCP** — live comp priors (win/pick rates, avg placement,
   tiers, unit rosters) layered onto the same patch via snapshot section
   inheritance.

Next sources by value: Riot match-v1 crawler (own data, real sample sizes,
conditional stats) → authorized MetaTFT access (rich per-rank breakdowns).
