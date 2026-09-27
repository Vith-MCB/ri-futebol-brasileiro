from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta a coleção SQLite para JSONL.")
    parser.add_argument("--db", default="data/coleta.db")
    parser.add_argument("--out", default="data/noticias.jsonl")
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"Banco não encontrado: {db}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    with out.open("w", encoding="utf-8") as fp:
        for row in conn.execute("SELECT * FROM documents ORDER BY id"):
            fp.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    conn.close()

    print(f"Exportado para: {out}")


if __name__ == "__main__":
    main()
