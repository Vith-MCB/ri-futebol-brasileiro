from src.url_utils import is_crawlable_url, normalize_url


def test_normalize_removes_tracking():
    url = normalize_url("https://EXAMPLE.com/a/?utm_source=x&b=2")
    assert url == "https://example.com/a/?b=2"


def test_rejects_image():
    assert not is_crawlable_url(
        "https://example.com/foto.jpg", {"example.com"}
    )


def test_accepts_subdomain():
    assert is_crawlable_url(
        "https://news.example.com/futebol/noticia", {"example.com"}
    )
