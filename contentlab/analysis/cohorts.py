"""
contentlab.analysis.cohorts  --  Per-year distribution aggregates with a
popularity control, plus era comparisons.

Reusable for any "score distribution by release year" anime analysis (score
inflation, the adaptation bump, studio fingerprints, ...). The article decides
which outputs to narrate.
"""
from . import stats


def yearly_aggregates(rows, *, value_key="average_score", year_key="year",
                      pop_key="popularity", pop_floor=5000,
                      fixed_score=85, top_q=0.90, year_start=None, year_end=None):
    """Return a list of per-year aggregate dicts, sorted by year.

    For each year: n, n_popular, mean/median (all + popular), stdev, the
    percentile rank of `fixed_score`, and the `top_q` cutoff (all + popular).
    "popular" = rows with pop_key >= pop_floor (controls for thin-sample noise).
    """
    def num(r, k):
        v = r.get(k)
        return float(v) if v not in (None, "") else None

    years = sorted({int(r[year_key]) for r in rows if r.get(year_key) not in (None, "")})
    if year_start is not None:
        years = [y for y in years if y >= year_start]
    if year_end is not None:
        years = [y for y in years if y <= year_end]

    out = []
    for year in years:
        yr = [r for r in rows if str(r.get(year_key)) == str(year) and num(r, value_key) is not None]
        scored = [num(r, value_key) for r in yr]
        if not scored:
            continue
        popular = [num(r, value_key) for r in yr
                   if (r.get(pop_key) not in (None, "")) and int(r[pop_key]) >= pop_floor]
        out.append({
            "year": year,
            "n": len(scored),
            "n_popular": len(popular),
            "mean": round(stats.mean(scored), 2),
            "median": round(stats.median(scored), 2),
            "mean_popular": round(stats.mean(popular), 2) if popular else None,
            "median_popular": round(stats.median(popular), 2) if popular else None,
            "stdev": round(stats.pstdev(scored), 2),
            "pct_rank_of_fixed": round(stats.pct_below(scored, fixed_score), 1),
            "pct_rank_of_fixed_popular": round(stats.pct_below(popular, fixed_score), 1) if popular else None,
            "topq_cutoff": round(stats.quantile(scored, top_q), 1),
            "topq_cutoff_popular": round(stats.quantile(popular, top_q), 1) if popular else None,
        })
    return out


def era_mean(yearly, key, y0, y1):
    """Mean of `key` across the per-year aggregates whose year is in [y0, y1]."""
    vals = [d[key] for d in yearly if y0 <= d["year"] <= y1 and d.get(key) is not None]
    return round(stats.mean(vals), 2) if vals else None


def _popular_scores(rows, *, value_key, year_key, pop_key, pop_floor, y0=None, y1=None):
    """Scores of the popular cohort, optionally restricted to release years [y0, y1]."""
    out = []
    for r in rows:
        if r.get(value_key) in (None, "") or r.get(pop_key) in (None, ""):
            continue
        if int(r[pop_key]) < pop_floor:
            continue
        if r.get(year_key) in (None, ""):
            continue
        y = int(r[year_key])
        if (y0 is not None and y < y0) or (y1 is not None and y > y1):
            continue
        out.append(float(r[value_key]))
    return out


def score_histogram(rows, y0, y1, *, value_key="average_score", year_key="year",
                    pop_key="popularity", pop_floor=5000, lo=30, hi=90, width=5):
    """Density histogram of popular-cohort scores released in [y0, y1].

    Returns (centers, density): `centers` are the bin midpoints, `density` is each
    bin's share of the era's titles as a percentage (so eras with different counts
    compare on the same vertical scale). Scores outside [lo, hi) fall into the edge
    bins. Used to draw a smoothed distribution curve per era.
    """
    n_bins = int(round((hi - lo) / width))
    centers = [round(lo + (i + 0.5) * width, 1) for i in range(n_bins)]
    counts = [0] * n_bins
    vals = _popular_scores(rows, value_key=value_key, year_key=year_key,
                           pop_key=pop_key, pop_floor=pop_floor, y0=y0, y1=y1)
    for v in vals:
        idx = int((v - lo) // width)
        idx = max(0, min(n_bins - 1, idx))
        counts[idx] += 1
    total = len(vals) or 1
    density = [round(100.0 * c / total, 2) for c in counts]
    return centers, density


def band_share_by_year(rows, lo, hi, *, value_key="average_score", year_key="year",
                       pop_key="popularity", pop_floor=5000,
                       year_start=None, year_end=None):
    """Per-year share (%) of the popular cohort scoring in the band [lo, hi].

    Returns a list of {year, share, n} sorted by year. Used to track whether a
    score band (e.g. the low-80s 'very good' tier) thickens over time.
    """
    years = sorted({int(r[year_key]) for r in rows if r.get(year_key) not in (None, "")})
    if year_start is not None:
        years = [y for y in years if y >= year_start]
    if year_end is not None:
        years = [y for y in years if y <= year_end]
    out = []
    for year in years:
        vals = _popular_scores(rows, value_key=value_key, year_key=year_key,
                               pop_key=pop_key, pop_floor=pop_floor, y0=year, y1=year)
        if not vals:
            continue
        in_band = sum(1 for v in vals if lo <= v <= hi)
        out.append({"year": year, "n": len(vals),
                    "share": round(100.0 * in_band / len(vals), 1)})
    return out
