#!/usr/bin/env python3
"""
run.py  --  Build (and optionally publish) the anime score-inflation post.

Thin consumer of contentlab: load data -> analyze -> build interactive chart ->
assemble post.html -> (optionally) create a Shopify draft.

  python posts/anime-score-inflation/run.py              # build outputs (no network)
  python posts/anime-score-inflation/run.py --refresh    # re-scrape AniList first
  python posts/anime-score-inflation/run.py --list-blogs # discover Shopify blog ids
  python posts/anime-score-inflation/run.py --publish    # create the draft (needs token)

Shopify env for --publish / --list-blogs:
  SHOPIFY_STORE (e.g. hakistop.myshopify.com), SHOPIFY_ADMIN_TOKEN (shpat_...),
  optional SHOPIFY_BLOG_ID or SHOPIFY_BLOG_HANDLE, optional SHOPIFY_API_VERSION.
Run from anywhere; paths resolve relative to this file. Talks to AniList/Shopify,
not the Anthropic API, so the --no-api cost rules don't apply.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Make contentlab/ importable regardless of CWD or layout. In the toolkit it lives
# at the repo root (two levels up); in an exported standalone article repo it sits
# beside this file. Prefer whichever location actually has the package, so an export
# uses its own vendored copy rather than the toolkit's.
HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
for _cand in (HERE, REPO):
    if (_cand / "contentlab" / "__init__.py").exists():
        sys.path.insert(0, str(_cand))
        break
sys.path.insert(0, str(HERE))   # config.py sits beside run.py in both layouts

from contentlab import dataset                                  # noqa: E402
from contentlab.analysis import cohorts                         # noqa: E402
from contentlab.charts import terminal                          # noqa: E402
from contentlab.publish.shopify import ShopifyAdmin, html_to_article  # noqa: E402
import config                                                   # noqa: E402  (same dir)

DATA = HERE / "data" / "anime_raw.csv"
OUT = HERE / "output"
NARRATIVE = HERE / "narrative.html"
EXCERPT = HERE / "excerpt.md"


def _sign(x):
    return f"+{x}" if (x is not None and x > 0) else f"{x}"


def load_or_refresh(refresh):
    if refresh:
        from contentlab.sources.anilist import fetch_anime
        print("[refresh] scraping AniList (~5-10 min)...")
        rows = fetch_anime(**config.QUERY, on_progress=lambda y, n: print(f"  {y}: {n}"))
        DATA.parent.mkdir(parents=True, exist_ok=True)
        dataset.write_csv(rows, DATA)
        print(f"[refresh] wrote {len(rows)} rows -> {DATA}")
        return rows
    if not DATA.exists():
        sys.exit(f"No cached data at {DATA}. Run with --refresh to scrape.")
    return dataset.read_csv(DATA)


def analyze(rows):
    a = config.ANALYSIS
    yearly = cohorts.yearly_aggregates(
        rows, value_key=a["value_key"], pop_floor=a["pop_floor"],
        fixed_score=a["fixed_score"], top_q=a["top_q"],
        year_start=config.QUERY["year_start"], year_end=config.QUERY["year_end"],
    )
    (e0, e1), (l0, l1) = config.ERAS["early"], config.ERAS["late"]
    em = lambda k: cohorts.era_mean(yearly, k, e0, e1)   # noqa: E731
    lm = lambda k: cohorts.era_mean(yearly, k, l0, l1)   # noqa: E731
    headline = {
        "mean_popular_early": em("mean_popular"), "mean_popular_late": lm("mean_popular"),
        "topq_cutoff_early": em("topq_cutoff_popular"), "topq_cutoff_late": lm("topq_cutoff_popular"),
        "pct_rank_early": em("pct_rank_of_fixed_popular"), "pct_rank_late": lm("pct_rank_of_fixed_popular"),
    }
    headline["mean_shift"] = round(headline["mean_popular_late"] - headline["mean_popular_early"], 2)
    headline["cutoff_shift"] = round(headline["topq_cutoff_late"] - headline["topq_cutoff_early"], 2)
    headline["rank_drift"] = round(headline["pct_rank_late"] - headline["pct_rank_early"], 1)
    return yearly, headline


SRC = "SOURCE: AniList GraphQL API"


def build_charts(rows, yearly, headline):
    """Build every chart in the post.

    Returns an ordered list of (token, fragment, iframe_title). The first entry is
    the main multi-test chart (token "{{CHART}}"); the rest are the supporting
    visuals that break up the article. Each token must appear in narrative.html.
    All run off the cached rows/yearly aggregates - no re-scrape.
    """
    years = [d["year"] for d in yearly]
    pick = lambda k: [d.get(k) for d in yearly]   # noqa: E731
    a = config.ANALYSIS
    (e0, e1) = config.ERAS["early"]
    (l0, l1) = config.ERAS["late"]
    y0, y1 = config.QUERY["year_start"], config.QUERY["year_end"]
    out = []

    # 1) MAIN: the three tests on one chart -------------------------------------
    # palette matches contentlab.charts.terminal.PALETTE (brand green, sand, periwinkle)
    main_sets = [
        {"label": "Mean score (popular)", "data": pick("mean_popular"), "color": "#46c98b", "axis": "left"},
        {"label": "Top-10% cutoff", "data": pick("topq_cutoff_popular"), "color": "#d9a441", "axis": "left"},
        {"label": "Where an 8.5 ranks", "data": pick("pct_rank_of_fixed_popular"),
         "color": "#7c9ce6", "axis": "right", "dashed": True},
    ]
    stat_cards = [
        {"k": "Mean, early vs late", "cls": "",
         "v": f'{headline["mean_popular_early"]} &rarr; {headline["mean_popular_late"]} ({_sign(headline["mean_shift"])})'},
        {"k": "Top-10% cutoff shift", "cls": "hkc-up" if headline["cutoff_shift"] >= 0 else "hkc-down",
         "v": f'{_sign(headline["cutoff_shift"])} pts'},
        {"k": 'An "8.5" percentile drift', "cls": "hkc-down" if headline["rank_drift"] <= 0 else "hkc-up",
         "v": f'{_sign(headline["rank_drift"])} pts'},
    ]
    out.append(("{{CHART}}", terminal.build_fragment(
        config.CHART_ID, years, main_sets,
        title="Anime Score Inflation - AniList",
        subtitle="TV anime - Japan - on 5,000+ user lists - by release year",
        source=SRC,
        left_axis_title="Score (0-100)", right_axis_title="Percentile of an 8.5",
        y_left=(60, 90), y_right=(90, 100),
        stat_cards=stat_cards,
        footnote=("Each point aggregates all qualifying TV anime released that year. "
                  "'Popular' = on at least 5,000 AniList users' lists. Mean and cutoff use "
                  "AniList's weighted averageScore; the dashed line is where a fixed 8.5 ranks."),
    ), "Anime score inflation, AniList 2000-2025"))

    # 2) VOLUME: more shows, same average ---------------------------------------
    out.append(("{{CHART_VOLUME}}", terminal.build_fragment(
        config.CHART_ID + "-volume", years,
        [{"label": "All TV anime", "data": pick("n"), "color": "#7c9ce6", "axis": "left"},
         {"label": "Popular (5,000+ lists)", "data": pick("n_popular"), "color": "#46c98b", "axis": "left"}],
        title="More Shows, Same Average",
        subtitle="TV anime released per year - all vs. popular",
        source=SRC,
        left_axis_title="Titles released",
        footnote=("The catalog grew sharply across the window while the mean score barely moved - "
                  "so the flat average isn't a small, stable scene holding still; it held as volume climbed."),
    ), "Anime released per year"))

    # 3) SPREAD: the distribution fanned out ------------------------------------
    out.append(("{{CHART_SPREAD}}", terminal.build_fragment(
        config.CHART_ID + "-spread", years,
        [{"label": "Std. deviation of scores", "data": pick("stdev"), "color": "#d9a441", "axis": "left"}],
        title="The Spread Widened",
        subtitle="Standard deviation of a year's scores",
        source=SRC,
        left_axis_title="Std. deviation (points)", y_left=(5, 11),
        footnote=("The typical gap between a year's shows grew from around 7 points in the late 2000s "
                  "to 9-10 by the early 2020s. The center held still; the edges pulled apart."),
    ), "Score spread by year"))

    # 4) DISTRIBUTION: center held, shape changed (early vs late) ----------------
    centers, early_d = cohorts.score_histogram(
        rows, e0, e1, value_key=a["value_key"], pop_floor=a["pop_floor"])
    _, late_d = cohorts.score_histogram(
        rows, l0, l1, value_key=a["value_key"], pop_floor=a["pop_floor"])
    out.append(("{{CHART_DISTRIBUTION}}", terminal.build_fragment(
        config.CHART_ID + "-dist", centers,
        [{"label": f"{e0}-{e1}", "data": early_d, "color": "#9a9a9a", "axis": "left"},
         {"label": f"{l0}-{l1}", "data": late_d, "color": "#46c98b", "axis": "left"}],
        title="The Center Held, The Shape Changed",
        subtitle="Score distribution of popular anime - early vs. late era",
        source=SRC,
        left_axis_title="Share of era's titles (%)",
        footnote=("Each curve is one era's popular titles binned by score (x-axis), as a share of that "
                  "era's total so the two compare fairly. The late-era curve is flatter and fatter at "
                  "both ends - more mass in the low 80s and more in the basement, a lower, broader peak "
                  "- yet its average lands in the same place as the early era's."),
    ), "Score distribution, early vs late era"))

    # 5) PILE-UP: the low-80s 'very good' band over time ------------------------
    band = cohorts.band_share_by_year(
        rows, 80, 84, value_key=a["value_key"], pop_floor=a["pop_floor"],
        year_start=y0, year_end=y1)
    out.append(("{{CHART_PILEUP}}", terminal.build_fragment(
        config.CHART_ID + "-pileup", [d["year"] for d in band],
        [{"label": "Share scoring 80-84", "data": [d["share"] for d in band], "color": "#46c98b", "axis": "left"}],
        title="Where The Pile-Up Is",
        subtitle="Share of popular anime in the low-80s 'very good' band",
        source=SRC,
        left_axis_title="% of year's popular titles",
        footnote=("The 80-84 band - 'really good' but short of an 8.5 - is a bigger slice of the field "
                  "now than it was. This is the thickening the eye-rollers feel, and it sits just below "
                  "the 85+ 'masterpiece' line, not at it."),
    ), "Low-80s band share by year"))

    return out


def _standalone(fragment):
    # standalone doc of just one chart (self-contained); also the srcdoc source.
    # transparent bg so it blends with the article page; the chart self-resizes.
    return (
        '<!DOCTYPE html><meta charset="utf-8">'
        "<style>html,body{margin:0;padding:0;background:transparent}</style>"
        f"<body>{fragment}</body>"
    )


def assemble(charts):
    """charts: list of (token, fragment, iframe_title); first is the main chart."""
    html = NARRATIVE.read_text(encoding="utf-8")
    for token, _frag, _t in charts:
        if token not in html:
            sys.exit(f"narrative.html is missing the {token} token.")
    OUT.mkdir(parents=True, exist_ok=True)

    # standalone doc of the main chart (kept as the canonical single-chart export)
    (OUT / "chart_standalone.html").write_text(_standalone(charts[0][1]), encoding="utf-8")

    # 1) inline variant: each chart's <script> sits in the body (for the Admin API
    #    path, which doesn't sanitize body_html)
    post_inline = html
    for token, frag, _t in charts:
        post_inline = post_inline.replace(token, f"<figure>\n{frag}\n</figure>")
    (OUT / "post.html").write_text(post_inline, encoding="utf-8")

    # 2) paste variant: each chart wrapped in its own <iframe srcdoc> so the script
    #    survives the Shopify editor's sanitizer. Cleaned to the body only (h1 lifted
    #    to the title field, <article> unwrapped) so it drops into the editor's HTML
    #    view without doubling the title the theme renders.
    paste_full = html
    for token, frag, iframe_title in charts:
        iframe = terminal.srcdoc_iframe(_standalone(frag), title=iframe_title)
        paste_full = paste_full.replace(token, f"<figure>\n{iframe}\n</figure>")
    title, paste_body = html_to_article(paste_full)
    (OUT / "post_paste.html").write_text(paste_body, encoding="utf-8")
    return title


def write_records(yearly, headline):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps({
        "config": {"query": config.QUERY, "analysis": config.ANALYSIS, "eras": config.ERAS},
        "headline": headline, "yearly": yearly,
    }, indent=2), encoding="utf-8")
    cols = list(yearly[0].keys())
    import csv
    with open(OUT / "yearly_stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(yearly)


def publish(do_write):
    store = os.environ.get("SHOPIFY_STORE")
    token = os.environ.get("SHOPIFY_ADMIN_TOKEN")
    if not (store and token):
        sys.exit("Set SHOPIFY_STORE and SHOPIFY_ADMIN_TOKEN (shpat_...) to publish.")
    admin = ShopifyAdmin(store, token, api_version=os.environ.get("SHOPIFY_API_VERSION", "2025-10"))
    title, body = html_to_article((OUT / "post.html").read_text(encoding="utf-8"))
    summary = EXCERPT.read_text(encoding="utf-8").strip() if EXCERPT.exists() else None
    print(f"Title:  {title}")
    print(f"Author: {config.AUTHOR}  | Tags: {config.TAGS or '(none)'}")
    print(f"Body:   {len(body)} chars | Excerpt: {summary!r}")
    if not do_write:
        print("\n[DRY RUN] add --publish to actually create the draft.")
        return
    blog_id = admin.resolve_blog_id(os.environ.get("SHOPIFY_BLOG_ID"), os.environ.get("SHOPIFY_BLOG_HANDLE"))
    art = admin.create_article(blog_id, title, body, summary_html=summary,
                               author=config.AUTHOR, tags=config.TAGS, published=False)
    print(f"\nCreated DRAFT article id={art.get('id')} in blog {blog_id} "
          f"(published={art.get('published_at') is not None}).")
    print(f"Edit: https://{admin.store}/admin/articles/{art.get('id')}")


def export_repo(title):
    """Export a self-contained public repo to repos/<slug>/ (toolkit-only)."""
    from contentlab.publish.repo_export import export_article
    slug = HERE.name
    dest = REPO / "repos" / slug
    summary = EXCERPT.read_text(encoding="utf-8").strip() if EXCERPT.exists() else ""
    github_url = f"https://github.com/{config.GITHUB_ORG}/{slug}"
    export_article(HERE, REPO / "contentlab", dest, title=title, summary=summary,
                   github_url=github_url, article_url=config.ARTICLE_URL,
                   include_data=True, force=True)
    print(f"\n--- export-repo ---\nWrote standalone public repo -> {dest}")
    print(f"  remote: {github_url}.git")


def main():
    ap = argparse.ArgumentParser(description="Build/publish the anime score-inflation post.")
    ap.add_argument("--refresh", action="store_true", help="Re-scrape AniList before building.")
    ap.add_argument("--list-blogs", action="store_true", help="List Shopify blogs and exit.")
    ap.add_argument("--publish", action="store_true", help="Create the Shopify draft (else dry run).")
    ap.add_argument("--export-repo", action="store_true",
                    help="Export a standalone public repo to repos/<slug>/.")
    args = ap.parse_args()

    if args.list_blogs:
        store, token = os.environ.get("SHOPIFY_STORE"), os.environ.get("SHOPIFY_ADMIN_TOKEN")
        if not (store and token):
            sys.exit("Set SHOPIFY_STORE and SHOPIFY_ADMIN_TOKEN to list blogs.")
        for b in ShopifyAdmin(store, token).list_blogs():
            print(f"  id={b['id']}  handle={b.get('handle')!r}  title={b.get('title')!r}")
        return

    rows = load_or_refresh(args.refresh)
    yearly, headline = analyze(rows)
    write_records(yearly, headline)
    charts = build_charts(rows, yearly, headline)
    title = assemble(charts)
    print("=== headline ===")
    for k, v in headline.items():
        print(f"  {k}: {v}")
    excerpt = EXCERPT.read_text(encoding="utf-8").strip() if EXCERPT.exists() else ""
    print("\n=== to paste manually into the Shopify blog editor (no token needed) ===")
    print(f"  Title (Title field):   {title}")
    print(f"  Excerpt (Excerpt field): {excerpt}")
    print(f"  Body (paste in the editor's <> HTML view): {OUT/'post_paste.html'}")
    print(f"\nAlso wrote: {OUT/'post.html'} (inline, for the API path), "
          f"{OUT/'results.json'}, {OUT/'yearly_stats.csv'}, {OUT/'chart_standalone.html'}")

    # exporting the public repo is opt-in and separate from building
    if args.export_repo:
        export_repo(title)

    # publishing is opt-in and separate from building
    if args.publish or os.environ.get("SHOPIFY_ADMIN_TOKEN"):
        print("\n--- Shopify ---")
        publish(args.publish)


if __name__ == "__main__":
    main()
