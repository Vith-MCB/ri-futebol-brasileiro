from src.classifier import is_brazilian_football, link_priority


def test_accepts_brazilian_football_news():
    ok, scores = is_brazilian_football(
        "Flamengo vence clássico pelo Brasileirão",
        "O Flamengo venceu a partida por 2 a 0 e assumiu a liderança da Série A.",
        "https://site.com/futebol/brasileirao/flamengo-vence",
    )
    assert ok
    assert scores["brazil_score"] >= 2


def test_rejects_other_sport():
    ok, _ = is_brazilian_football(
        "NBA: time vence partida nos playoffs",
        "Basquete internacional em destaque nesta rodada.",
        "https://site.com/basquete/nba",
    )
    assert not ok


def test_prioritizes_football_link():
    assert link_priority("https://site.com/futebol/brasileirao/flamengo") > 0
