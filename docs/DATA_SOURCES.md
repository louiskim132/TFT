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
| MetaBot.GG MCP | Live comp/stat summaries (tier lists, win/pick rates) | Public MCP endpoint, no auth, ~60 rpm | Candidate stats adapter |
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

## MetaBot.GG MCP (candidate)

- **Endpoint:** `https://metabot.gg/api/mcp` — streamable-HTTP MCP.
- **Verified:** 2026-09-13, `initialize` handshake succeeds with no auth.
  Exposes read-only tools incl. `get_team_comp` for TFT.
- **Fields:** comp names with win/pick rates and builds; oriented toward
  per-question answers rather than bulk export.
- **Access/terms:** public and read-only, ~60 req/min/IP plus a global
  ceiling. Citation/attribution requested.
- **Verdict:** viable secondary adapter for spot-checking priors, not ideal
  as the bulk ingestion source.

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

**First adapter: Community Dragon**, populating the unit/trait/item catalog
tables per patch. Comp performance priors stay on the fixture snapshot until
a stats source with confirmed access (MetaBot for spot checks now; Riot
crawler or authorized MetaTFT access later) is wired in.
