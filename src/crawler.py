from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import aiohttp

from .classifier import is_brazilian_football, link_priority
from .config import AppConfig
from .extractor import extract_document
from .fetcher import Fetcher
from .models import FrontierItem
from .robots import RobotsManager
from .storage import Storage
from .sitemaps import SitemapDiscoverer
from .url_utils import is_crawlable_url, normalize_url


class FocusedCrawler:
    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = Storage(config.crawler.database_path)
        self.allowed_domains = config.allowed_domains
        self.cutoff = datetime.now(timezone.utc) - timedelta(days=config.crawler.max_age_days)
        self.semaphore = asyncio.Semaphore(config.crawler.concurrency)

    def seed(self) -> None:
        for source in self.config.sources:
            url = normalize_url(source.seed)
            if url:
                self.storage.add_frontier(
                    FrontierItem(url=url, depth=0, priority=100, source_url=None)
                )

    def _enqueue_links(self, links: list[tuple[str, str]], source_url: str, depth: int) -> int:
        if depth >= self.config.crawler.max_depth:
            return 0
        added = 0
        for url, anchor in links:
            if not is_crawlable_url(url, self.allowed_domains):
                continue
            priority = link_priority(url, anchor)
            # Em profundidade inicial aceitamos links editoriais relacionados.
            # Depois disso, exigimos sinal temático para manter o crawler focado.
            if depth >= 1 and priority <= 0:
                continue
            if self.storage.add_frontier(
                FrontierItem(
                    url=url,
                    depth=depth + 1,
                    priority=priority,
                    source_url=source_url,
                )
            ):
                added += 1
        return added

    async def _process(self, item: FrontierItem, fetcher: Fetcher) -> None:
        async with self.semaphore:
            try:
                status, html, final_url = await fetcher.fetch(item.url)
                normalized_final = normalize_url(final_url) or item.url
                if not is_crawlable_url(normalized_final, self.allowed_domains):
                    self.storage.mark_done(item.url)
                    return

                doc, meta, links = extract_document(html, normalized_final, status)
                self._enqueue_links(links, normalized_final, item.depth)

                if doc is None:
                    self.storage.mark_done(item.url)
                    return

                if len(doc.text) < self.config.crawler.min_text_chars:
                    self.storage.mark_done(item.url)
                    return

                published_at = doc.published_at
                if published_at is None and not self.config.crawler.allow_unknown_date:
                    self.storage.mark_done(item.url)
                    return
                if published_at is not None and published_at < self.cutoff:
                    self.storage.mark_done(item.url)
                    return

                # Evita armazenar páginas de seção/listagem sem características de artigo.
                if not meta.get("is_article"):
                    self.storage.mark_done(item.url)
                    return

                accepted, _scores = is_brazilian_football(doc.title, doc.text, doc.canonical_url)
                if accepted:
                    self.storage.save_document(doc)

                self.storage.mark_done(item.url)

            except PermissionError as exc:
                self.storage.mark_failed(item.url, "robots", str(exc))
            except Exception as exc:
                self.storage.mark_failed(item.url, type(exc).__name__, str(exc))

    async def run(self) -> None:
        self.seed()
        headers = {
            "User-Agent": self.config.crawler.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
        }
        connector = aiohttp.TCPConnector(limit=max(16, self.config.crawler.concurrency * 2))

        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            robots = RobotsManager(
                session=session,
                user_agent=self.config.crawler.user_agent,
                default_delay=self.config.crawler.per_domain_delay_seconds,
            )
            fetcher = Fetcher(
                session=session,
                robots=robots,
                respect_robots=self.config.crawler.respect_robots_txt,
                timeout_seconds=self.config.crawler.request_timeout_seconds,
                max_retries=self.config.crawler.max_retries,
            )

            if self.config.crawler.discover_sitemaps:
                discoverer = SitemapDiscoverer(
                    session=session,
                    robots=robots,
                    storage=self.storage,
                    allowed_domains=self.allowed_domains,
                    cutoff=self.cutoff,
                    max_files_per_domain=self.config.crawler.sitemap_max_files_per_domain,
                    max_urls_total=self.config.crawler.sitemap_max_urls_total,
                )
                total_added = 0
                seen_origins: set[str] = set()
                for source in self.config.sources:
                    parts = urlsplit(source.seed)
                    origin = f"{parts.scheme}://{parts.netloc}"
                    if origin in seen_origins:
                        continue
                    seen_origins.add(origin)
                    added = await discoverer.discover_from_seed(source.seed)
                    total_added += added
                    print(f"[sitemap] {parts.netloc}: +{added} URLs temáticas")
                print(f"[sitemap] total descoberto: {total_added} URLs\n")

            while self.storage.document_count() < self.config.crawler.target_documents:
                batch = self.storage.claim_batch(self.config.crawler.batch_size)
                if not batch:
                    break

                await asyncio.gather(*(self._process(item, fetcher) for item in batch))

                docs = self.storage.document_count()
                frontier = self.storage.frontier_counts()
                print(
                    f"[coleta] documentos={docs} | "
                    f"pendentes={frontier.get('pending', 0)} | "
                    f"concluidas={frontier.get('done', 0)} | "
                    f"falhas={frontier.get('failed', 0)}"
                )

        print("\nColeta encerrada.")
        print(f"Documentos armazenados: {self.storage.document_count()}")
        print(f"Critério-alvo: {self.config.crawler.target_documents}")
        print(f"Fronteira: {self.storage.frontier_counts()}")
        self.storage.close()
