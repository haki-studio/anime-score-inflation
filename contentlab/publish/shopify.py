"""
contentlab.publish.shopify  --  Reusable Shopify Admin API publisher.

Create/update blog articles (as drafts by default) from a post's HTML. stdlib only.

    from contentlab.publish.shopify import ShopifyAdmin, html_to_article
    admin = ShopifyAdmin(store, token)            # token is shpat_... (NOT api key/secret)
    title, body = html_to_article(open("post.html").read())
    admin.create_article(blog_id, title, body, summary_html=excerpt,
                         author="Devin", published=False)

Auth: pass an Admin API access token (starts with `shpat_`) used in the
`X-Shopify-Access-Token` header. The app's API key + secret are OAuth client
credentials and CANNOT authenticate Admin calls directly.
Scopes needed: read_content, write_content.
"""
import json
import re
import urllib.error
import urllib.request

DEFAULT_API_VERSION = "2025-10"


class ShopifyError(RuntimeError):
    pass


def html_to_article(html):
    """Turn a finalized post HTML doc/fragment into (title, body_html).

    Strips HTML comments, lifts the first <h1> out as the title (themes render
    article.title separately, so leaving it in the body would duplicate it),
    and unwraps a top-level <article> tag.
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        raise ShopifyError("no <h1> found to use as the article title")
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
    body = (html[:m.start()] + html[m.end():])
    body = re.sub(r"</?article[^>]*>", "", body, flags=re.IGNORECASE).strip()
    return title, body


class ShopifyAdmin:
    def __init__(self, store, token, api_version=DEFAULT_API_VERSION, timeout=30):
        if not store or not token:
            raise ShopifyError("store and token are required")
        self.store = store.replace("https://", "").rstrip("/")
        self.token = token
        self.api_version = api_version
        self.timeout = timeout

    def _request(self, method, path, body=None):
        url = f"https://{self.store}/admin/api/{self.api_version}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Shopify-Access-Token": self.token,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:800]
            raise ShopifyError(f"{method} {path} -> {e.code}: {detail}")

    def list_blogs(self):
        return self._request("GET", "blogs.json").get("blogs", [])

    def resolve_blog_id(self, blog_id=None, handle=None):
        if blog_id:
            return int(blog_id)
        blogs = self.list_blogs()
        if handle:
            for b in blogs:
                if b.get("handle") == handle:
                    return b["id"]
            raise ShopifyError(f"no blog with handle {handle!r}; have: "
                               + ", ".join(f"{b['handle']}({b['id']})" for b in blogs))
        if len(blogs) == 1:
            return blogs[0]["id"]
        raise ShopifyError("multiple blogs; pass blog_id or handle. "
                           + "Have: " + ", ".join(f"{b['handle']}({b['id']})" for b in blogs))

    def create_article(self, blog_id, title, body_html, *, summary_html=None,
                       author=None, tags=None, published=False):
        article = {"title": title, "body_html": body_html, "published": published}
        if summary_html:
            article["summary_html"] = summary_html
        if author:
            article["author"] = author
        if tags:
            article["tags"] = tags
        res = self._request("POST", f"blogs/{blog_id}/articles.json", {"article": article})
        return res.get("article", {})
