from __future__ import annotations

import argparse
import sqlite3
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Mostra estatísticas da coleta.")
    parser.add_argument("--db", default="data/coleta.db")
    args = parser.parse_args()

    path = Path(args.db)
    if not path.exists():
        raise SystemExit(f"Banco não encontrado: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM frontier WHERE status='pending'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM frontier WHERE status='failed'").fetchone()[0]

    print(f"Documentos válidos: {total}")
    print(f"URLs pendentes: {pending}")
    print(f"URLs com falha: {failed}\n")

    print("Por domínio:")
    for row in conn.execute(
        "SELECT domain, COUNT(*) AS n FROM documents GROUP BY domain ORDER BY n DESC"
    ):
        print(f"  {row['domain']:<30} {row['n']:>8}")

    print("\nDatas:")
    row = conn.execute(
        "SELECT MIN(published_at) AS oldest, MAX(published_at) AS newest FROM documents"
    ).fetchone()
    print(f"  Mais antiga: {row['oldest']}")
    print(f"  Mais recente: {row['newest']}")

    print("\nPrincipais erros:")
    counts = Counter(
        row["error_type"] for row in conn.execute("SELECT error_type FROM errors")
    )
    for error_type, n in counts.most_common(10):
        print(f"  {error_type:<25} {n:>8}")

    conn.close()


if __name__ == "__main__":
    main()
