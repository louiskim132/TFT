# Scoring

`Score(s, a) = baseline(a) + Σ weight_i · feature_i(s, a)`

Every `ScoredAction` retains its full feature vector (name, raw value, weight,
contribution, human reason) — inspectable now, ML training table later.

## Baselines are shrunk priors

Raw upstream statistics are never trusted at face value. Placement/top4/win
are shrunk toward the symmetric lobby constants (placement 4.5, top4 0.5,
win 0.125 — exact means for an 8-player lobby):

    adjusted = n/(n+k) · observed + k/(n+k) · prior     (k = 250)

A comp averaging 2.9 on 40 games lands near ~4.3, not 2.9 — it cannot leap
a comp averaging 4.0 on 50k games. Constants (not a computed comp mean) are
used so an extreme observation cannot drag its own prior down with it.

`sample_reliability` (n/(n+k)) is recorded in every comp feature vector at
weight 0 — present for a future learned model, not double-counted now.

## Features in use

### PLAY_COMP (via `CompEvaluator`)

| feature | direction | meaning |
| --- | --- | --- |
| `core_unit_overlap` | + | fraction of core units owned |
| `upgraded_core_overlap` | + | owned core already 2★+ |
| `optional_unit_overlap` | + | flex pieces owned |
| `item_fit` | + | completed items ∩ preferred |
| `trait_continuity` | + | comp traits already active on board |
| `gold_cost_to_core` | − | est. cost of missing core units (catalog costs) |
| `level_gap` | − | comp's typical level above player's |
| `contest` | − | lobby summary + per-opponent likely_comp signals |
| `transition_cost` | − | share of current board dead to this comp |
| `low_hp_immediacy` | + (hp≤30) | near-complete lines get urgency bonus |

### ROLL

`hp_urgency` (≤25 strong +, ≤40 mild +, ≥80 −), `econ_cost` (− at ≥20g/≥30g
spend), `interest_preservation` (+ when stopping at ≥50g).

### BUY

`upgrade_potential` (+ owns a copy), `comp_flexibility` (+ unit in N comps),
`low_gold_purchase_cost` (− drops below 10g), `unit_contest` (− copies held
by opponents, from summary or per-opponent scouting).

### HOLD

`max_interest` (+ ≥50g), `healthy_hp_greed` (+ ≥70hp), `critical_hp_risk`
(− ≤25hp).

### CHOOSE_AUGMENT

Augment strength is **derived**, not looked up — no accessible source
publishes per-augment stats. `augments.py` compares the state against guide
benchmarks (level pacing curve, expected gold, expected items per stage;
comp `typical_level` overrides the curve for roll lines) and produces a
`NeedProfile`: normalized deficits for xp/econ/items. Each offered augment is
classified by name keyword into ECON/XP/ITEM/TRAIT/COMBAT.

| feature | direction | meaning |
| --- | --- | --- |
| `need_match` | + | augment's category vs. that category's deficit |
| `comp_augment_fit` | + | augment listed in a comp's `augment_preferences` |
| `trait_on_board` | + | emblem/crest matches a trait already on board |

## Confidence

Currently `sigmoid(|score|)` — an explicit placeholder. Phase 9 (margin- and
reliability-aware confidence, gating Tier-2 search) is not implemented yet.

## Tuning contract

Any weight change must keep `python -m evaluation.runner` at zero
catastrophic decisions and pass `pytest`. New behavior gets a scenario or a
unit test first.
