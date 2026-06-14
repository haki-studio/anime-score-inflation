"""
contentlab.publish.github  --  Minimal GitHub REST helper (stdlib urllib).

Just enough to set a public repo's "About" metadata after exporting it. Needs a
token with `repo` (or fine-grained "Administration: write") scope, read from the
`GITHUB_TOKEN` / `GH_TOKEN` env var. Git/SSH can push commits but cannot set the
description - that is repo metadata, only reachable via the API.

    from contentlab.publish.github import set_repo_metadata
    set_repo_metadata("haki-studio", "anime-score-inflation",
                      description="...", homepage="https://...", token=tok)
"""
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def get_token(explicit=None):
    return explicit or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def set_repo_metadata(owner, repo, *, description=None, homepage=None,
                      token=None, api=API):
    """PATCH a repo's description / homepage. Returns the updated repo JSON.

    Only fields that are not None are sent. Raises GitHubError on failure (incl.
    a missing token, so callers can fall back to printing a manual command).
    """
    token = get_token(token)
    if not token:
        raise GitHubError("no GITHUB_TOKEN / GH_TOKEN in env")
    payload = {k: v for k, v in (("description", description), ("homepage", homepage))
               if v is not None}
    if not payload:
        raise GitHubError("nothing to update (description and homepage both None)")
    req = urllib.request.Request(
        f"{api}/repos/{owner}/{repo}", data=json.dumps(payload).encode(),
        method="PATCH", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "haki-content-lab",
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise GitHubError(f"PATCH repo failed ({e.code}): "
                          f"{e.read().decode(errors='replace')[:300]}")
