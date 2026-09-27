from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
try:
    import trafilatura
except ImportError:  # fallback simples; requirements.txt instala a versão completa
    trafilatura = None

from .models import Document
from .url_utils import normalize_url


def _first_meta(soup: BeautifulSoup, keys: Iterable[tuple[str, str]]) -> str | None:
    for attr, value in keys:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            return str(tag.get("content")).strip()
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = date_parser.parse(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _json_ld_objects(soup: BeautifulSoup):
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list):
            yield from obj
        elif isinstance(obj, dict):
            if isinstance(obj.get("@graph"), list):
                yield from obj["@graph"]
            yield obj


def extract_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = _first_meta(soup, (("property", "og:title"), ("name", "twitter:title")))
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else None
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    canonical = None
    canonical_tag = soup.find("link", rel=lambda x: x and "canonical" in x)
    if canonical_tag and canonical_tag.get("href"):
        canonical = normalize_url(str(canonical_tag.get("href")), base=url)

    description = _first_meta(
        soup,
        (("property", "og:description"), ("name", "description"), ("name", "twitter:description")),
    )
    author = _first_meta(soup, (("name", "author"), ("property", "article:author")))
    published = _first_meta(
        soup,
        (
            ("property", "article:published_time"),
            ("name", "date"),
            ("name", "pubdate"),
            ("itemprop", "datePublished"),
        ),
    )
    article_type = _first_meta(soup, (("property", "og:type"),))

    for obj in _json_ld_objects(soup):
        obj_type = obj.get("@type")
        if isinstance(obj_type, list):
            types = {str(x).lower() for x in obj_type}
        else:
            types = {str(obj_type).lower()}
        if {"newsarticle", "article", "reportagenewsarticle"} & types:
            title = title or obj.get("headline") or obj.get("name")
            description = description or obj.get("description")
            published = published or obj.get("datePublished")
            if not author:
                author_obj = obj.get("author")
                if isinstance(author_obj, dict):
                    author = author_obj.get("name")
                elif isinstance(author_obj, list) and author_obj:
                    first = author_obj[0]
                    author = first.get("name") if isinstance(first, dict) else str(first)
            article_type = article_type or "article"

    return {
        "title": re.sub(r"\s+", " ", title or "").strip(),
        "canonical_url": canonical or normalize_url(url) or url,
        "description": description.strip() if description else None,
        "author": author.strip() if author else None,
        "published_at": _parse_date(published),
        "is_article": bool(article_type and "article" in article_type.lower()) or bool(published),
        "soup": soup,
    }


def extract_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag in soup.find_all("a", href=True):
        normalized = normalize_url(str(tag.get("href")), base=base_url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        anchor = tag.get_text(" ", strip=True)
        results.append((normalized, anchor[:250]))
    return results


def extract_document(html: str, url: str, status_code: int) -> tuple[Document | None, dict, list[tuple[str, str]]]:
    meta = extract_metadata(html, url)
    links = extract_links(meta["soup"], url)

    if trafilatura is not None:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            include_links=False,
            favor_precision=True,
            output_format="txt",
        ) or ""
    else:
        # Fallback para ambientes em que a dependência ainda não foi instalada.
        soup = meta["soup"]
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        container = (
            soup.find("article")
            or soup.find(attrs={"itemprop": "articleBody"})
            or soup.find("main")
            or soup.body
            or soup
        )
        text = container.get_text("\n", strip=True)

    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not meta["title"] or not text:
        return None, meta, links

    normalized_for_hash = re.sub(r"\s+", " ", text.lower()).strip()
    content_hash = hashlib.sha256(normalized_for_hash.encode("utf-8")).hexdigest()
    canonical = meta["canonical_url"]

    doc = Document(
        url=url,
        canonical_url=canonical,
        domain=urlsplit(canonical).netloc.lower(),
        title=meta["title"],
        author=meta["author"],
        description=meta["description"],
        published_at=meta["published_at"],
        collected_at=datetime.now(timezone.utc),
        text=text,
        content_hash=content_hash,
        status_code=status_code,
    )
    return doc, meta, links
