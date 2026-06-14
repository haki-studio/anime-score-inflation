"""
contentlab.analysis.stats  --  Generic distribution helpers (stdlib only).

Small, reusable primitives used to build per-article analyses. Nothing here is
specific to score inflation; these are the building blocks.
"""
import statistics as _st


def mean(values):
    return _st.mean(values) if values else None


def median(values):
    return _st.median(values) if values else None


def pstdev(values):
    return _st.pstdev(values) if len(values) > 1 else 0.0


def pct_below(values, x):
    """Percentile position of x within values (0-100): share scoring strictly below x."""
    if not values:
        return None
    return 100.0 * sum(1 for v in values if v < x) / len(values)


def quantile(values, q):
    """Linear-interpolated q-quantile (q in [0,1]). Matches numpy's default 'linear'."""
    if not values:
        return None
    s = sorted(values)
    idx = q * (len(s) - 1)
    lo = int(idx)
    frac = idx - lo
    if lo + 1 < len(s):
        return s[lo] * (1 - frac) + s[lo + 1] * frac
    return s[lo]
