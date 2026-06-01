from app.services.document_extraction_service import chunk_text, extract_chunks
from pathlib import Path
import tempfile
import os


def test_chunk_text_short_passthrough():
    text = "Hello world"
    assert chunk_text(text) == ["Hello world"]


def test_chunk_text_splits_long_text():
    text = "x" * 2000
    chunks = chunk_text(text, max_chars=800, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 800 for c in chunks)


def test_chunk_text_overlap():
    text = "a" * 1000
    chunks = chunk_text(text, max_chars=500, overlap=50)
    # Second chunk should start 450 chars in (500 - 50 overlap)
    assert len(chunks) == 3  # 0-500, 450-950, 900-1000


def test_chunk_text_filters_empty():
    # chunk_text itself doesn't filter, but extract_chunks does
    text = "  "
    chunks = chunk_text(text)
    assert chunks == ["  "]  # chunk_text doesn't filter, that's extract_chunks's job


def test_extract_chunks_txt():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("This is a test document with some content.\n" * 5)
        tmp_path = f.name
    try:
        chunks = extract_chunks(tmp_path, "txt")
        assert len(chunks) >= 1
        assert all(len(c) >= 30 for c in chunks)
    finally:
        os.unlink(tmp_path)


def test_extract_chunks_unknown_type_returns_empty():
    chunks = extract_chunks("/nonexistent/file.xyz", "xyz")
    assert chunks == []
