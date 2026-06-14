"""
contentlab.sources.anilist  --  Reusable AniList GraphQL client.

Reusable across any anime article: pull media by year range / format / country
without rebuilding a scraper each time. stdlib only.

    from contentlab.sources.anilist import fetch_anime
    rows = fetch_anime(2000, 2025, fmt="TV", country="JP",
                       on_progress=lambda y, n: print(y, n))

Notes
-----
* AniList sits behind Cloudflare, which 403s the default ``python-urllib``
  User-Agent. A descriptive UA is REQUIRED and is sent by default below.
* AniList rate-limits (~90/min, sometimes degraded to 30/min). We sleep between
  requests and honour Retry-After on 429s; 5xx are retried.
"""
import json
import time
import urllib.error
import urllib.request

ENDPOINT = "https://graphql.anilist.co"
DEFAULT_UA = "HakiStudiosBot/1.0 (content-lab; +https://hakistop.com)"

# One media row per anime, normalized to flat snake_case. Reused by analysis.
MEDIA_QUERY = """
query ($year: Int, $page: Int, $perPage: Int, $format: MediaFormat, $country: CountryCode) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage currentPage }
    media(seasonYear: $year, type: ANIME, format: $format, countryOfOrigin: $country, sort: ID) {
      id
      idMal
      title { romaji english }
      seasonYear
      season
      episodes
      averageScore
      meanScore
      popularity
      favourites
      genres
      source
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""


class AniListError(RuntimeError):
    pass


class AniListClient:
    """Thin, rate-limit-aware POST client for the AniList GraphQL API."""

    def __init__(self, user_agent=DEFAULT_UA, timeout=30, max_tries=6):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_tries = max_tries

    def query(self, query, variables):
        body = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            ENDPOINT, data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self.user_agent,   # load-bearing: Cloudflare 403s without it
            },
        )
        for attempt in range(self.max_tries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = int(e.headers.get("Retry-After", "60"))
                    time.sleep(wait + 1)
                    continue
                if e.code >= 500:
                    time.sleep(5)
                    continue
                raise
            except urllib.error.URLError:
                time.sleep(5)
        raise AniListError("too many retries")


def _flatten(media):
    studios = (media.get("studios") or {}).get("nodes", []) or []
    title = media.get("title") or {}
    return {
        "id": media["id"],
        "id_mal": media.get("idMal"),
        "title": (title.get("english") or title.get("romaji") or "").strip(),
        "year": media.get("seasonYear"),
        "season": media.get("season"),
        "episodes": media.get("episodes"),
        "average_score": media.get("averageScore"),   # 0-100, weighted
        "mean_score": media.get("meanScore"),          # 0-100, raw mean
        "popularity": media.get("popularity"),         # users with it on a list
        "favourites": media.get("favourites"),
        "genres": media.get("genres") or [],
        "source": media.get("source"),
        "studio": studios[0]["name"] if studios else "",
    }


def fetch_anime(year_start, year_end, fmt="TV", country="JP",
                sleep=1.4, client=None, on_progress=None):
    """Fetch all anime in [year_start, year_end] as a list of flat row dicts.

    fmt/country map to AniList MediaFormat / CountryCode. on_progress(year, count)
    is called once per year if provided.
    """
    client = client or AniListClient()
    rows = []
    for year in range(year_start, year_end + 1):
        page, year_count = 1, 0
        while True:
            data = client.query(MEDIA_QUERY, {
                "year": year, "page": page, "perPage": 50,
                "format": fmt, "country": country,
            })
            if "errors" in data:
                raise AniListError(f"{year} p{page}: {data['errors']}")
            block = data["data"]["Page"]
            for m in block["media"]:
                rows.append(_flatten(m))
                year_count += 1
            if not block["pageInfo"]["hasNextPage"]:
                break
            page += 1
            time.sleep(sleep)
        if on_progress:
            on_progress(year, year_count)
        time.sleep(sleep)
    return rows
