from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlsplit

import aiohttp
from dateutil import parser as date_parser

from .classifier import link_priority
from .models import FrontierItem
from .robots import RobotsManager
from .storage import Storage
from .url_utils import is_crawlable_url, normalize_url


class SitemapDiscoverer:
    """Descobre URLs recentes a partir de sitemaps declarados no robots.txt."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        robots: RobotsManager,
        storage: Storage,
        allowed_domains: set[str],
        cutoff: datetime,
        max_files_per_domain: int = 80,
        max_urls_total: int = 150000,
    ):
        self.session = session
        self.robots = robots
        self.storage = storage
        self.allowed_domains = allowed_domains
        self.cutoff = cutoff
        self.max_files_per_domain = max_files_per_domain
        self.max_urls_total = max_urls_total

    async def _read_bytes(self, url: str) -> bytes | None:
        try:
            await self.robots.wait_turn(url)
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, timeout=timeout, allow_redirects=True) as response:
                if response.status >= 400:
                    return None
                data = await response.read()
                if len(data) > 25 * 1024 * 1024:
                    return None
                if url.lower().endswith(".gz") or response.headers.get("content-type", "").lower().find("gzip") >= 0:
                    try:
                        data = gzip.decompress(data)
                    except OSError:
                        pass
                return data
        except Exception:
            return None

    async def _declared_sitemaps(self, seed: str) -> list[str]:
        parts = urlsplit(seed)
        origin = f"{parts.scheme}://{parts.netloc}"
        robots_url = origin + "/robots.txt"
        data = await self._read_bytes(robots_url)
        if not data:
            return [origin + "/sitemap.xml"]
        text = data.decode("utf-8", errors="ignore")
        found = re.findall(r"(?im)^\s*Sitemap\s*:\s*(https?://\S+)\s*$", text)
        return list(dict.fromkeys(found)) or [origin + "/sitemap.xml"]

    @staticmethod
    def _lastmod_is_recent(value: str | None, cutoff: datetime) -> bool:
        if not value:
            return True
        try:
            dt = date_parser.parse(value)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc) >= cutoff
        except Exception:
            return True

    async def discover_from_seed(self, seed: str) -> int:
        queue = deque(await self._declared_sitemaps(seed))
        visited: set[str] = set()
        added = 0
        files = 0

        while queue and files < self.max_files_per_domain and added < self.max_urls_total:
            sitemap_url = normalize_url(queue.popleft())
            if not sitemap_url or sitemap_url in visited:
                continue
            visited.add(sitemap_url)
            files += 1

            data = await self._read_bytes(sitemap_url)
            if not data:
                continue

            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue

            root_name = root.tag.rsplit("}", 1)[-1].lower()
            if root_name == "sitemapindex":
                for node in root:
                    loc = node.findtext("{*}loc")
                    lastmod = node.findtext("{*}lastmod")
                    if loc and self._lastmod_is_recent(lastmod, self.cutoff):
                        queue.append(loc.strip())
                continue

            if root_name != "urlset":
                continue

            for node in root:
                loc = node.findtext("{*}loc")
                lastmod = node.findtext("{*}lastmod")
                if not loc or not self._lastmod_is_recent(lastmod, self.cutoff):
                    continue
                url = normalize_url(loc.strip())
                if not url or not is_crawlable_url(url, self.allowed_domains):
                    continue
                priority = link_priority(url)
                if priority <= 0:
                    continue
                if self.storage.add_frontier(
                    FrontierItem(url=url, depth=1, priority=max(10, priority), source_url=sitemap_url)
                ):
                    added += 1
                    if added >= self.max_urls_total:
                        break

        return added
