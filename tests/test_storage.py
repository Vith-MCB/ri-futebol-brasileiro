from datetime import datetime, timezone

from src.models import Document, FrontierItem
from src.storage import Storage


def test_storage_checkpoint_and_dedup(tmp_path):
    storage = Storage(str(tmp_path / "coleta.db"))
    assert storage.add_frontier(FrontierItem("https://example.com/a", 0, 10))
    assert not storage.add_frontier(FrontierItem("https://example.com/a", 0, 10))

    batch = storage.claim_batch(1)
    assert len(batch) == 1
    storage.mark_done(batch[0].url)

    doc = Document(
        url="https://example.com/a",
        canonical_url="https://example.com/a",
        domain="example.com",
        title="Flamengo vence",
        author=None,
        description=None,
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        text="texto " * 200,
        content_hash="abc123",
        status_code=200,
    )
    assert storage.save_document(doc)
    assert not storage.save_document(doc)
    assert storage.document_count() == 1
    storage.close()
