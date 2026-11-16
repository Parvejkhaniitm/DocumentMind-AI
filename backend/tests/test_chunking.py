import re

from app.core.config import settings
from app.services.chunking import chunk_text


class WordOffsetTokenizer:
    def __call__(self, text, **_kwargs):
        return {
            "offset_mapping": [(match.start(), match.end()) for match in re.finditer(r"\S+", text)]
        }


def test_chunking_overlaps_windows_and_keeps_source_words(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_chunk_tokens", 4)
    monkeypatch.setattr(settings, "embedding_chunk_overlap", 1)
    text = "Alpha one. Bravo two. Charlie three. Delta four."

    chunks = chunk_text(text, WordOffsetTokenizer())

    assert chunks[0] == "Alpha one. Bravo two."
    assert len(chunks) >= 3
    assert "two." in chunks[1]
    assert "four." in chunks[-1]
    assert all(chunk.strip() == chunk and chunk for chunk in chunks)


def test_chunking_handles_empty_and_single_token_inputs(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_chunk_tokens", 4)
    monkeypatch.setattr(settings, "embedding_chunk_overlap", 1)
    tokenizer = WordOffsetTokenizer()

    assert chunk_text("  \n", tokenizer) == []
    assert chunk_text("Only.", tokenizer) == ["Only."]


def test_chunking_makes_progress_when_overlap_is_zero(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_chunk_tokens", 2)
    monkeypatch.setattr(settings, "embedding_chunk_overlap", 0)

    chunks = chunk_text("one two three four", WordOffsetTokenizer())

    assert chunks == ["one two", "three four"]
