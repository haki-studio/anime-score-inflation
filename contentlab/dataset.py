"""
contentlab.dataset  --  Canonical CSV schema + read/write for scraped media rows.

One flat schema shared by the scraper output and the analysis input, so cached
pulls are reusable across articles without per-post column wrangling.
"""
import csv

FIELDS = [
    "id", "id_mal", "title", "year", "season", "episodes",
    "average_score", "mean_score", "popularity", "favourites",
    "genres", "source", "studio",
]


def write_csv(rows, path):
    """Write rows (genres may be a list) to the canonical CSV schema."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            row = dict(r)
            g = row.get("genres")
            if isinstance(g, list):
                row["genres"] = "|".join(g)
            w.writerow({k: ("" if row.get(k) is None else row.get(k, "")) for k in FIELDS})


def read_csv(path):
    """Read the canonical CSV back to a list of dict rows (values as strings)."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))
