from __future__ import annotations

import posixpath
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "output", "cmpid"
}

BLOCKED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".rar", ".7z", ".mp3", ".wav", ".mp4", ".avi",
    ".mov", ".mkv", ".css", ".js", ".xml"
}

BLOCKED_PATH_HINTS = (
    "/login", "/cadastro", "/assine", "/newsletter", "/contato",
    "/politica-de-privacidade", "/termos", "/autor/", "/tag/", "/tags/",
    "/videos/", "/video/", "/fotos/", "/galeria/", "/podcast/"
)


def normalize_url(url: str, base: str | None = None) -> str | None:
    if base:
        url = urljoin(base, url)

    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None

    host = parts.netloc.lower().split(":")[0]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    path = posixpath.normpath(path)
    if not path.startswith("/"):
        path = "/" + path
    if parts.path.endswith("/") and path != "/":
        path += "/"

    query_pairs = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_pairs))

    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def host_matches(host: str, allowed_domains: set[str]) -> bool:
    host = host.lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def is_crawlable_url(url: str, allowed_domains: set[str]) -> bool:
    parts = urlsplit(url)
    if not host_matches(parts.netloc, allowed_domains):
        return False

    path_lower = parts.path.lower()
    if any(path_lower.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        return False
    if any(hint in path_lower for hint in BLOCKED_PATH_HINTS):
        return False
    return True
