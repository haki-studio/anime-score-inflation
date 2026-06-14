"""Config for the 'Does an 8.5 Today Mean What It Did in 2010?' post.

The post is a thin consumer of contentlab: this file holds only the knobs; all
logic lives in the reusable package.
"""

# AniList pull (only used with run.py --refresh; otherwise data/anime_raw.csv is loaded)
QUERY = dict(year_start=2000, year_end=2025, fmt="TV", country="JP")

# Analysis knobs
ANALYSIS = dict(value_key="average_score", pop_floor=5000, fixed_score=85, top_q=0.90)

# Era windows compared in the headline
ERAS = dict(early=(2005, 2009), late=(2020, 2024))

# Chart
CHART_ID = "hk-anime-score-inflation"

# Shopify
AUTHOR = "Devin"
TAGS = None          # skipped for now

# Public per-article repo (run.py --export-repo). Slug is the post dir name.
GITHUB_ORG = "haki-studio"
ARTICLE_URL = None   # set to the published blog URL once live; shown in the repo README
