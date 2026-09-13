"""Sample-size-aware reliability adjustment.

Observed statistics are shrunk toward a broader prior so that small samples
with extreme values cannot dominate decisions:

    adjusted = n/(n+k) * observed + k/(n+k) * prior

`k` is the pseudo-count: roughly how many observations of prior evidence the
field mean is worth. k=250 means a comp needs ~250 recorded games before its
own numbers outweigh the patch-wide average.
"""

from __future__ import annotations

DEFAULT_PSEUDOCOUNT = 250.0


def shrinkage_weight(sample_size: int | float, k: float = DEFAULT_PSEUDOCOUNT) -> float:
    """How much of the observed value survives; 0 = pure prior, 1 = pure data."""
    n = max(0.0, float(sample_size))
    return n / (n + k)


def shrunk_value(
    observed: float,
    sample_size: int | float,
    prior: float,
    k: float = DEFAULT_PSEUDOCOUNT,
) -> float:
    w = shrinkage_weight(sample_size, k)
    return w * observed + (1.0 - w) * prior
