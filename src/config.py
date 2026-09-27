from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class SourceConfig:
    name: str
    seed: str
    domains: list[str]


@dataclass(slots=True)
class CrawlerConfig:
    target_documents: int
    max_age_days: int
    concurrency: int
    per_domain_delay_seconds: float
    request_timeout_seconds: int
    max_retries: int
    max_depth: int
    batch_size: int
    min_text_chars: int
    respect_robots_txt: bool
    allow_unknown_date: bool
    user_agent: str
    database_path: str
    discover_sitemaps: bool
    sitemap_max_files_per_domain: int
    sitemap_max_urls_total: int


@dataclass(slots=True)
class AppConfig:
    crawler: CrawlerConfig
    sources: list[SourceConfig]

    @property
    def allowed_domains(self) -> set[str]:
        return {domain.lower() for source in self.sources for domain in source.domains}


def _require(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"Campo obrigatório ausente no config.yaml: {key}")
    return mapping[key]


def load_config(path: str | Path) -> AppConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp)

    c = _require(raw, "crawler")
    crawler = CrawlerConfig(
        target_documents=int(_require(c, "target_documents")),
        max_age_days=int(_require(c, "max_age_days")),
        concurrency=int(_require(c, "concurrency")),
        per_domain_delay_seconds=float(_require(c, "per_domain_delay_seconds")),
        request_timeout_seconds=int(_require(c, "request_timeout_seconds")),
        max_retries=int(_require(c, "max_retries")),
        max_depth=int(_require(c, "max_depth")),
        batch_size=int(_require(c, "batch_size")),
        min_text_chars=int(_require(c, "min_text_chars")),
        respect_robots_txt=bool(_require(c, "respect_robots_txt")),
        allow_unknown_date=bool(_require(c, "allow_unknown_date")),
        user_agent=str(_require(c, "user_agent")),
        database_path=str(_require(c, "database_path")),
        discover_sitemaps=bool(c.get("discover_sitemaps", True)),
        sitemap_max_files_per_domain=int(c.get("sitemap_max_files_per_domain", 80)),
        sitemap_max_urls_total=int(c.get("sitemap_max_urls_total", 150000)),
    )

    sources = [
        SourceConfig(
            name=str(_require(item, "name")),
            seed=str(_require(item, "seed")),
            domains=[str(d).lower() for d in _require(item, "domains")],
        )
        for item in _require(raw, "sources")
    ]

    return AppConfig(crawler=crawler, sources=sources)
