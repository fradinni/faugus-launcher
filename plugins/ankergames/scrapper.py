"""
Scrapper for AnkerGames game pages.

Responsibilities:
- Fetch a game page URL
- Extract the latest version string from a <span> element whose class list
  contains all of: "animate-glow", "text-white", "bg-green-500"

No third-party dependencies are used to keep the plugin self-contained.
"""
from __future__ import annotations

import re
import urllib.request
import urllib.error

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def fetch_url(url: str, timeout: float = 10.0) -> str:
    """Fetch URL contents as text using urllib with a browser-like UA.

    Returns empty string on error.
    """
    if not url:
        return ""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return ""


def extract_version_from_html(html: str) -> str:
    """Extract the version string from HTML.

    Looks for a <span ...> whose class attribute contains the three
    classes: animate-glow, text-white, bg-green-500.

    Returns the text content stripped, or empty string if not found.
    """
    if not html:
        return ""

    # Simplistic and resilient regex-based extraction. We search for spans
    # that have all three classes in any order and with possible duplicates.
    # Then we capture their inner text content (non-greedy until closing span).
    span_regex = re.compile(
        r"<span[^>]*class=\"(?=[^\"]*\banimate-glow\b)(?=[^\"]*\btext-white\b)(?=[^\"]*\bbg-green-500\b)[^\"]*\"[^>]*>(.*?)</span>",
        re.IGNORECASE | re.DOTALL,
    )

    m = span_regex.search(html)
    if not m:
        return ""
    inner = m.group(1)
    # Remove HTML tags inside and unescape entities in a minimal way
    inner = re.sub(r"<[^>]+>", "", inner)
    inner = (inner or "").strip()
    # Unescape a few common entities without external deps
    inner = (
        inner.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return inner.strip()


def get_latest_version(url: str, timeout: float = 10.0) -> str:
    """Fetch URL and return the extracted latest version string.

    Returns empty string when version cannot be determined.
    """
    html = fetch_url(url, timeout=timeout)
    return extract_version_from_html(html)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version-like strings.

    Returns:
    -1 if v1 < v2, 0 if equal, 1 if v1 > v2. Unknown/empty values are treated
    as the lowest.
    """
    def tokenize(v: str):
        if not v:
            return []
        # Split into numeric and alpha sequences
        parts = re.findall(r"\d+|[A-Za-z]+|[^A-Za-z0-9]+", v)
        tokens = []
        for p in parts:
            if p.isdigit():
                tokens.append((0, int(p)))
            elif p.isalpha():
                tokens.append((1, p.lower()))
            else:
                # separators weigh less than alpha
                tokens.append((2, p))
        return tokens

    t1, t2 = tokenize(v1), tokenize(v2)
    for a, b in zip(t1, t2):
        if a == b:
            continue
        return -1 if a < b else 1
    # If all shared tokens equal, longer list is greater if it has significant tokens
    if len(t1) == len(t2):
        return 0
    return -1 if len(t1) < len(t2) else 1
