from src.extractor import extract_document


def test_extracts_article_and_links():
    html = '''
    <html lang="pt-BR"><head>
      <meta property="og:type" content="article">
      <meta property="og:title" content="Flamengo vence pelo Brasileirão">
      <meta property="article:published_time" content="2026-09-27T12:00:00-03:00">
      <link rel="canonical" href="https://example.com/futebol/flamengo-vence">
    </head><body>
      <article><p>O Flamengo venceu a partida pelo Campeonato Brasileiro.</p>
      <p>O time marcou dois gols e assumiu a liderança da competição nacional.</p></article>
      <a href="/futebol/brasileirao/proxima-noticia">Próxima notícia</a>
    </body></html>
    '''
    doc, meta, links = extract_document(html, "https://example.com/futebol/x", 200)
    assert doc is not None
    assert meta["is_article"] is True
    assert doc.title == "Flamengo vence pelo Brasileirão"
    assert doc.published_at is not None
    assert any("proxima-noticia" in url for url, _ in links)
