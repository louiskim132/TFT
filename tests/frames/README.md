# Held-out labeled frames

41 shop-bar screenshots (Korean client, set 18, ~1240x207) + one JSON
sidecar each. **Do not tune CV matchers against these** — report accuracy
only. They exist so every perception claim has an honest measurement.

## Fields per sidecar

| Field | Status |
| --- | --- |
| `shop` (5 slots, null = empty) | labeled |
| `level`, `xp.current/max` | labeled (`xp: null` at level 10, no XP shown) |
| `gold` | labeled |
| `streak.count/color` | labeled (`orange`/`blue`/`none`; sign convention unverified) |
| `shop_odds` | visible in bar, not yet labeled — derivable from `level` |

Not visible in these bars: stage/round, own HP, items, bench, board.
Full-frame labels are a separate task (S1).

## Caveat

The `shop` labels here were also the calibration corpus for
`data/card_templates/18/` — shop matching on these is in-sample
(`flags.shop_calibration_in_sample`). HUD fields (gold/level/xp/streak)
were never tuned against them, so they are a valid holdout for S1 work.
New screenshots should extend this set as true holdouts.
