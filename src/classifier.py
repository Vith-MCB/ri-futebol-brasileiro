from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

BRAZIL_CLUBS = {
    "america mg", "athletico pr", "atletico go", "atletico mg", "avai", "bahia",
    "botafogo", "bragantino", "ceara", "chapecoense", "corinthians", "coritiba",
    "crb", "criciuma", "cruzeiro", "cuiaba", "flamengo", "fluminense", "fortaleza",
    "goias", "gremio", "internacional", "juventude", "mirassol", "nautico", "paysandu",
    "ponte preta", "remo", "santa cruz", "santos", "sao paulo", "sport", "vasco",
    "vitoria", "vila nova"
}

FOOTBALL_TERMS = {
    "futebol", "jogo", "partida", "gol", "gols", "tecnico", "treinador", "atacante",
    "goleiro", "zagueiro", "lateral", "meia", "volante", "camisa", "torcida", "estadio",
    "arbitragem", "var", "contratacao", "mercado da bola", "transferencia"
}

BRAZIL_TERMS = {
    "brasileirao", "brasileiro serie a", "serie a", "serie b", "serie c", "serie d",
    "copa do brasil", "cbf", "selecao brasileira", "futebol brasileiro", "libertadores",
    "sul americana", "paulista", "carioca", "mineiro", "gaucho", "nordestao"
}

NEGATIVE_SPORTS = {
    "nba", "basquete", "volei", "tenis", "formula 1", "f1", "mma", "ufc", "nfl",
    "futebol americano", "motogp", "stock car"
}

URL_GOOD_HINTS = (
    "futebol", "brasileirao", "brasileiro", "copa-do-brasil", "libertadores",
    "selecao-brasileira", "mercado-da-bola", "times", "clubes", "serie-a", "serie-b"
)


def fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def link_priority(url: str, anchor: str = "") -> int:
    parts = urlsplit(url)
    haystack = fold(parts.path + " " + parts.query + " " + anchor)
    score = 0
    if any(term in haystack for term in URL_GOOD_HINTS):
        score += 4
    if any(term in haystack for term in BRAZIL_TERMS):
        score += 3
    if any(club.replace(" ", "-") in haystack or club in haystack for club in BRAZIL_CLUBS):
        score += 3
    pagination_terms = ("proxima", "próxima", "next", "ver mais", "carregar mais", "page=", "pagina=")
    if any(term in haystack for term in pagination_terms):
        score += 2
    if any(term in haystack for term in NEGATIVE_SPORTS):
        score -= 6
    return score


def is_brazilian_football(title: str, text: str, url: str = "") -> tuple[bool, dict[str, int]]:
    # O título recebe peso maior porque páginas esportivas podem conter menus
    # com termos de outras modalidades no corpo HTML.
    title_f = fold(title)
    sample_f = fold((text or "")[:12000])
    url_f = fold(url)

    football_score = 0
    brazil_score = 0
    negative_score = 0

    for term in FOOTBALL_TERMS:
        if term in title_f:
            football_score += 3
        elif term in sample_f:
            football_score += 1

    # URLs editoriais costumam carregar o contexto da seção mesmo quando a
    # manchete não contém a palavra "futebol".
    if any(term in url_f for term in URL_GOOD_HINTS):
        football_score += 3

    for term in BRAZIL_TERMS:
        if term in title_f or term in url_f:
            brazil_score += 3
        elif term in sample_f:
            brazil_score += 1

    for club in BRAZIL_CLUBS:
        if club in title_f:
            brazil_score += 4
        elif club in sample_f:
            brazil_score += 1

    for term in NEGATIVE_SPORTS:
        if term in title_f:
            negative_score += 4

    accepted = football_score >= 2 and brazil_score >= 2 and negative_score < 4
    return accepted, {
        "football_score": football_score,
        "brazil_score": brazil_score,
        "negative_score": negative_score,
    }
