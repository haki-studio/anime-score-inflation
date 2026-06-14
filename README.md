# Does an 8.5 Today Mean What It Did in 2010?

The reproducible analysis behind the Haki Studios article **"Does an 8.5 Today Mean What It Did in 2010?"**.

> I pulled 3,476 AniList scores to test a fan gripe: has an 8.5 inflated since 2010? The average barely moved - but the top of the scale tells on itself.

This repo is a frozen snapshot of the code and data that produced the article. It
runs on the Python 3 **standard library only** - no `pip install`.

## Run it

```bash
python run.py
```

Uses the cached AniList pull in `data/`; pass `--refresh` to re-scrape. Outputs are written to `output/`:
- `post.html` - the full article body with the interactive charts inlined.
- `post_paste.html` - the same body with each chart wrapped in an `<iframe srcdoc>`.
- `results.json` + `yearly_stats.csv` - every number in the post, traceable.

## What's inside

- `run.py` - one entrypoint: load -> analyze -> build charts -> assemble.
- `config.py` - the knobs for this analysis (query, popularity floor, eras).
- `narrative.html` - the written post, with `{{CHART...}}` tokens for the charts.
- `data/anime_raw.csv` - cached AniList pull, so the analysis is reproducible offline.
- `contentlab/` - vendored copy of the stdlib-only analysis + chart toolkit.

`output/` is created when you run it (the deliverables above) and is gitignored -
this repo ships source + data, not generated artifacts.

## Data

Scores are from the [AniList](https://anilist.co) GraphQL API (TV anime, Japan,
release years per `config.py`). "Score" is AniList's weighted `averageScore`. The
cached pull reflects list counts at scrape time.

## License

Code is MIT licensed (see `LICENSE`). Data is sourced from AniList under their terms.

A Haki Studios data-journalism project.
