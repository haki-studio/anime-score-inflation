"""
contentlab.sinks.supabase  --  Optional Supabase/Postgres sink for scraped rows.

Reusable shared store so multiple articles query one dataset instead of
re-scraping AniList every time. Upserts on the primary key via the PostgREST
REST API (stdlib urllib, no deps), so re-runs refresh rows in place.

    from contentlab.sinks.supabase import upsert
    upsert(rows)   # reads SUPABASE_URL / SUPABASE_KEY / SUPABASE_TABLE from env

Rows are canonical dataset dicts (see contentlab.dataset). `genres` may be a list
or a "|"-joined string; it is sent as a JSON array for a Postgres text[] column.
Schema: db/schema.sql (apply once). Needs the service-role key.
"""
import json
import os
import urllib.error
import urllib.request

CHUNK = 500


class SupabaseError(RuntimeError):
    pass


def _record(r):
    g = r.get("genres")
    if isinstance(g, str):
        g = [x for x in g.split("|") if x]
    elif g is None:
        g = []
    rec = {k: r.get(k) for k in (
        "id", "id_mal", "title", "year", "season", "episodes",
        "average_score", "mean_score", "popularity", "favourites", "source", "studio")}
    rec["genres"] = g
    return rec


def upsert(rows, *, url=None, key=None, table=None, chunk=CHUNK):
    url = url or os.environ.get("SUPABASE_URL")
    key = key or os.environ.get("SUPABASE_KEY")
    table = table or os.environ.get("SUPABASE_TABLE", "anime_raw")
    if not (url and key):
        raise SupabaseError("SUPABASE_URL and SUPABASE_KEY (service-role) are required")
    endpoint = f"{url.rstrip('/')}/rest/v1/{table}"
    headers = {
        "Content-Type": "application/json",
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "resolution=merge-duplicates,return=minimal",  # upsert on PK
    }
    records = [_record(r) for r in rows]
    sent = 0
    for i in range(0, len(records), chunk):
        batch = records[i:i + chunk]
        req = urllib.request.Request(endpoint, data=json.dumps(batch).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            raise SupabaseError(f"upsert failed ({e.code}): {e.read().decode(errors='replace')[:500]}")
        sent += len(batch)
    return sent
