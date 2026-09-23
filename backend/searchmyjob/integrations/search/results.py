"""[Sol] Bounded Google redirect resolution and explicit search-response validation."""

import asyncio
from urllib.parse import parse_qs, urlsplit

import httpx


def public_url(value):
    if not isinstance(value, str):
        return ""
    try:
        u = urlsplit(value.strip())
        return (
            value.strip()
            if u.scheme in ("https", "http") and u.hostname and not u.username and not u.password
            else ""
        )
    except ValueError:
        return ""


def search_query(criteria):
    if criteria.get("_platform") in ("linkedin", "indeed"):
        return f"{criteria['_platform']} · {criteria['keywords']} · {criteria.get('location', '')} · {criteria.get('country', 'fr').upper()}"
    from searchmyjob.domain.search_quality import targeted_query

    return targeted_query(criteria)


def normalize_link(link):
    if not isinstance(link, str):
        return ""
    # Only recognized Google paths can be interpreted relative to the search origin.
    if link.startswith(("/goto?", "/url?")):
        link = "https://www.google.com" + link
    link = public_url(link)
    if not link:
        return ""
    u = urlsplit(link)
    if u.hostname in ("google.com", "www.google.com") and u.path == "/url":
        params = parse_qs(u.query)
        direct = public_url((params.get("q") or params.get("url") or [""])[0])
        if direct:
            return direct
    return link


def is_google_redirect(url):
    u = urlsplit(url)
    return (
        u.scheme == "https"
        and u.hostname in ("www.google.com", "google.com")
        and u.port in (None, 443)
        and u.path in ("/goto", "/url")
    )


async def resolve_results(items, client=None):
    """One GET to Google per distinct wrapper, no follow to the destination, no API key."""
    if client is None:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as c:
            return await resolve_results(items, c)
    sem = asyncio.Semaphore(5)
    links = {normalize_link(x.get("link", "")) for x in items[:30] if isinstance(x, dict)}

    async def resolve(link):
        if not link or not is_google_redirect(link):
            return link, link
        async with sem:
            try:
                r = await client.get(link, follow_redirects=False)
                target = (
                    public_url(r.headers.get("location", ""))
                    if r.status_code in (301, 302, 303, 307, 308)
                    else ""
                )
                return link, target or link
            except httpx.HTTPError:
                return link, link

    resolved = dict(await asyncio.gather(*(resolve(link) for link in links)))
    rows = []
    for x in items[:30]:
        if not isinstance(x, dict):
            continue
        link = normalize_link(x.get("link", ""))
        target = resolved.get(link, link)
        if target and isinstance(x.get("title"), str) and x["title"].strip():
            rows.append({**x, "link": target, "google_redirect": is_google_redirect(target)})
    return rows
