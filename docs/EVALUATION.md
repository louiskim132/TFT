# Evaluation

## Harness

`evaluation/scenarios/*.json` — deterministic scenarios:

```json
{
  "name": "critical_hp_should_stabilize",
  "category": "econ",
  "importance": "high",
  "state": { "...": "GameState payload" },
  "expected":     [{"type": "roll"}],
  "unacceptable": [{"type": "hold"}]
}
```

An action matches a spec when its type and every specified field match.
`expected` = acceptable top actions; `unacceptable` = catastrophic if top-1.

## Run

```bash
python -m evaluation.runner                      # fixture snapshot
python -m evaluation.runner --db data/tft.db     # real ingested snapshot
```

Metrics: per-scenario flag (`OK`/`top3`/`MISS`/`CATASTROPHIC`), top-1 rate,
top-3 rate, catastrophic count, mean/max latency. Exit code 1 if any
catastrophic pick — CI-usable.

## Current baseline (fixture snapshot)

    top1: 80%   top3: 100%   catastrophic: 0   mean latency ~0.2ms

## Dataset separation (planned, not yet enforced mechanically)

- **development**: the committed `scenarios/` — used while tuning weights.
- **sealed holdout**: to be added; never inspected per-failure during tuning.
- **shadow**: real states captured after deployment (`decision logging`).

## Regression rule

Every behavioral bug becomes a named scenario before the fix lands. Example:
`001_critical_hp_rolldown` guards "hold 42g at 18hp with a weak board".

## Not yet implemented

- Decision-regret scoring (`V(best) − V(chosen)`) — needs a value model.
- Confidence calibration tracking.
- Per-category breakdowns and importance weighting in the report (the fields
  exist on each scenario; aggregation is next).
