from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import EMBEDDING_DIMENSION, settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
    from transformers import PreTrainedTokenizerFast


class EmbeddingConfigurationError(ValueError):
    """The configured model does not match the persisted vector schema."""


class SearchQueryTooLong(ValueError):
    """The query exceeds the model's safe input length."""


@lru_cache(maxsize=1)
def get_tokenizer() -> PreTrainedTokenizerFast:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(settings.embedding_model, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise EmbeddingConfigurationError("The configured model needs a fast tokenizer for chunk boundaries.")
    return tokenizer


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(settings.embedding_model)
    dimension = model.get_sentence_embedding_dimension()
    if dimension != EMBEDDING_DIMENSION:
        raise EmbeddingConfigurationError(
            f"Model produces {dimension} dimensions; database expects {EMBEDDING_DIMENSION}."
        )
    if settings.embedding_chunk_overlap >= settings.embedding_chunk_tokens:
        raise EmbeddingConfigurationError("Chunk overlap must be smaller than the chunk token limit.")
    if settings.embedding_chunk_tokens + 2 > model.max_seq_length:
        raise EmbeddingConfigurationError(
            "Chunk token limit plus model special tokens exceeds the model's input limit."
        )
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.astype("float32").tolist()


def embed_query(query: str) -> list[float]:
    tokenizer = get_tokenizer()
    token_ids = tokenizer.encode(query, add_special_tokens=False)
    model = get_embedding_model()
    max_query_tokens = model.max_seq_length - 2
    if len(token_ids) > max_query_tokens:
        raise SearchQueryTooLong(f"Search query is too long; use at most {max_query_tokens} model tokens.")
    return embed_texts([query])[0]
