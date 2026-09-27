from __future__ import annotations

import asyncio
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp


class RobotsManager:
    def __init__(self, session: aiohttp.ClientSession, user_agent: str, default_delay: float):
        self.session = session
        self.user_agent = user_agent
        self.default_delay = default_delay
        self.parsers: dict[str, RobotFileParser] = {}
        self.crawl_delays: dict[str, float] = {}
        self.domain_locks: dict[str, asyncio.Lock] = {}
        self.last_request_started: dict[str, float] = {}

    async def _load(self, url: str) -> tuple[RobotFileParser, float]:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self.parsers:
            return self.parsers[origin], self.crawl_delays[origin]

        robots_url = origin + "/robots.txt"
        parser = RobotFileParser(robots_url)
        delay = self.default_delay
        try:
            async with self.session.get(robots_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status < 400:
                    text = await response.text(errors="ignore")
                    parser.parse(text.splitlines())
                    robots_delay = parser.crawl_delay(self.user_agent) or parser.crawl_delay("*")
                    if robots_delay is not None:
                        delay = max(delay, float(robots_delay))
                else:
                    parser.parse([])
        except Exception:
            # Na dúvida, não inventamos bloqueios. O crawler continua com a
            # latência mínima configurada e registra erros de página normalmente.
            parser.parse([])

        self.parsers[origin] = parser
        self.crawl_delays[origin] = delay
        return parser, delay

    async def allowed(self, url: str) -> bool:
        parser, _ = await self._load(url)
        return parser.can_fetch(self.user_agent, url)

    async def wait_turn(self, url: str) -> None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        _, delay = await self._load(url)
        lock = self.domain_locks.setdefault(origin, asyncio.Lock())
        async with lock:
            elapsed = time.monotonic() - self.last_request_started.get(origin, 0.0)
            wait_for = max(0.0, delay - elapsed)
            if wait_for:
                await asyncio.sleep(wait_for)
            self.last_request_started[origin] = time.monotonic()
