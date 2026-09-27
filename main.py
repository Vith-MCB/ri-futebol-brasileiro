from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.config import load_config
from src.crawler import FocusedCrawler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coletor focado de notícias recentes do futebol brasileiro."
    )
    parser.add_argument("--config", default="config.yaml", help="Arquivo YAML de configuração")
    parser.add_argument("--target", type=int, help="Sobrescreve o alvo de documentos")
    parser.add_argument("--days", type=int, help="Sobrescreve a janela de recência em dias")
    parser.add_argument("--concurrency", type=int, help="Sobrescreve a concorrência global")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Configuração não encontrada: {config_path}")

    config = load_config(config_path)
    if args.target is not None:
        config.crawler.target_documents = args.target
    if args.days is not None:
        config.crawler.max_age_days = args.days
    if args.concurrency is not None:
        config.crawler.concurrency = args.concurrency

    print("RI Futebol Brasileiro — Coletor")
    print(f"Alvo: {config.crawler.target_documents} documentos")
    print(f"Janela: últimos {config.crawler.max_age_days} dias")
    print(f"Domínios permitidos: {len(config.allowed_domains)}")
    print(f"Banco: {config.crawler.database_path}\n")

    asyncio.run(FocusedCrawler(config).run())


if __name__ == "__main__":
    main()
