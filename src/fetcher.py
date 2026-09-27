from __future__ import annotations

import asyncio

import aiohttp

from .robots import RobotsManager


class Fetcher:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        robots: RobotsManager,
        respect_robots: bool,
        timeout_seconds: int,
        max_retries: int,
    ):
        self.session = session
        self.robots = robots
        self.respect_robots = respect_robots
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.max_retries = max_retries

    async def fetch(self, url: str) -> tuple[int, str, str]:
        if self.respect_robots and not await self.robots.allowed(url):
            raise PermissionError("URL bloqueada pelo robots.txt")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                await self.robots.wait_turn(url)
                async with self.session.get(url, timeout=self.timeout, allow_redirects=True) as response:
                    content_type = response.headers.get("content-type", "").lower()
                    if response.status >= 400:
                        raise RuntimeError(f"HTTP {response.status}")
                    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                        raise TypeError(f"Conteúdo não HTML: {content_type}")
                    html = await response.text(errors="ignore")
                    return response.status, html, str(response.url)
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(2 ** attempt)

        assert last_error is not None
        raise last_error
