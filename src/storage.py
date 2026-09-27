from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Document, FrontierItem


class Storage:
    def __init__(self, path: str):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._create_schema()
        self.requeue_interrupted()

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS frontier (
                url TEXT PRIMARY KEY,
                depth INTEGER NOT NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                added_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_frontier_status_priority
                ON frontier(status, priority DESC, depth ASC, added_at ASC);

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                canonical_url TEXT NOT NULL UNIQUE,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                description TEXT,
                published_at TEXT,
                collected_at TEXT NOT NULL,
                text TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                status_code INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_documents_published_at ON documents(published_at);
            CREATE INDEX IF NOT EXISTS idx_documents_domain ON documents(domain);

            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                error_type TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def requeue_interrupted(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE frontier SET status='pending', updated_at=? WHERE status='processing'",
            (now,),
        )
        self.conn.commit()

    def add_frontier(self, item: FrontierItem) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """
            INSERT OR IGNORE INTO frontier(url, depth, priority, source_url, status, added_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (item.url, item.depth, item.priority, item.source_url, now, now),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def claim_batch(self, limit: int) -> list[FrontierItem]:
        rows = self.conn.execute(
            """
            SELECT url, depth, priority, source_url
            FROM frontier
            WHERE status='pending'
            ORDER BY priority DESC, depth ASC, added_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        if not rows:
            return []

        now = datetime.now(timezone.utc).isoformat()
        self.conn.executemany(
            "UPDATE frontier SET status='processing', updated_at=? WHERE url=?",
            [(now, row["url"]) for row in rows],
        )
        self.conn.commit()
        return [FrontierItem(**dict(row)) for row in rows]

    def mark_done(self, url: str) -> None:
        self.conn.execute(
            "UPDATE frontier SET status='done', updated_at=? WHERE url=?",
            (datetime.now(timezone.utc).isoformat(), url),
        )
        self.conn.commit()

    def mark_failed(self, url: str, error_type: str, message: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE frontier SET status='failed', updated_at=? WHERE url=?",
            (now, url),
        )
        self.conn.execute(
            "INSERT INTO errors(url, error_type, message, created_at) VALUES (?, ?, ?, ?)",
            (url, error_type, message[:2000], now),
        )
        self.conn.commit()

    def save_document(self, doc: Document) -> bool:
        try:
            self.conn.execute(
                """
                INSERT INTO documents(
                    url, canonical_url, domain, title, author, description,
                    published_at, collected_at, text, content_hash, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.url,
                    doc.canonical_url,
                    doc.domain,
                    doc.title,
                    doc.author,
                    doc.description,
                    doc.published_at.isoformat() if doc.published_at else None,
                    doc.collected_at.isoformat(),
                    doc.text,
                    doc.content_hash,
                    doc.status_code,
                ),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def document_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])

    def frontier_counts(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS n FROM frontier GROUP BY status"
        ).fetchall()
        return {row["status"]: row["n"] for row in rows}

    def close(self) -> None:
        self.conn.close()
