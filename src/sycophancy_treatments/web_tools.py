"""Optional local SearXNG search adapter; self-host to avoid commercial search API.

SearXNG still contacts upstream search engines; public-topic queries may leave ETH.
A guarded public-page reader follows search results; not a security boundary.
"""
from __future__ import annotations
import os
from urllib.parse import urlparse
import httpx


def searxng_search(query: str) -> list[dict]:
    url = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888")
    parsed = urlparse(url)
    if parsed.scheme not in ("http","https") or not parsed.netloc:
        raise ValueError("Invalid SEARXNG_URL")
    with httpx.Client(timeout=12.0, follow_redirects=False) as client:
        response = client.get(url.rstrip("/") + "/search",
                              params={"q":query,"format":"json","language":"en"})
        response.raise_for_status()
        data = response.json()
    return [{"title":str(x.get("title","")),"url":str(x.get("url","")),
             "content":str(x.get("content",""))} for x in data.get("results",[])[:4]]


# This parser strips HTML markup and scripts. The feature is limited to the
# public URLs already returned by SearXNG; it is not an arbitrary URL endpoint.
from html.parser import HTMLParser
import ipaddress
import socket


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def read_public_search_result(url: str, *, max_chars: int = 2800) -> str:
    """Best-effort page text. Reject direct private-network hosts.

    Not hardened for untrusted participant requests: do not expose a general
    URL-fetch endpoint or use before an ETH privacy and network security review.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Unsupported public URL")
    if parsed.port not in (None, 80, 443):
        raise ValueError("Nonstandard network port")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme=="https" else 80))
        if not addresses:
            raise ValueError("Cannot resolve URL")
        for rec in addresses:
            address = ipaddress.ip_address(rec[4][0])
            if not address.is_global:
                raise ValueError("Refusing non-public network address")
    except socket.gaierror as exc:
        raise ValueError("Cannot resolve URL") from exc
    with httpx.Client(timeout=6, follow_redirects=False, headers={"User-Agent":"SurveyResearchAgent/0.1"}) as client:
        with client.stream("GET", url) as res:
            res.raise_for_status()
            if res.status_code >= 300:
                raise ValueError("Redirects disabled")
            if "text/html" not in res.headers.get("content-type", "").lower():
                raise ValueError("Not an HTML page")
            data = bytearray()
            for chunk in res.iter_bytes():
                data.extend(chunk)
                if len(data)>200_000:
                    break
    parser = _TextOnly()
    parser.feed(bytes(data).decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())[:max_chars]


def search_and_read(query: str) -> list[dict]:
    """Search open web, then inspect up to two public HTML search hits."""
    results = searxng_search(query)
    for result in results[:2]:
        try:
            full_text = read_public_search_result(result["url"])
            if full_text:
                result["content"] = full_text
        except (httpx.HTTPError, ValueError, UnicodeError, OSError):
            # Preserve the SearXNG snippet for paywalled or unsupported pages.
            pass
    return results
