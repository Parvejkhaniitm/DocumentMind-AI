from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerFast

SENTENCE_END = frozenset(".!?")


def chunk_text(text: str, tokenizer: PreTrainedTokenizerFast) -> list[str]:
    """Split one source unit into overlapping, word-aligned tokenizer windows."""
    encoded = tokenizer(
        text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        truncation=False,
    )
    offsets = encoded["offset_mapping"]
    if not offsets:
        return []

    chunks: list[str] = []
    start = 0
    token_count = len(offsets)
    target_size = settings.embedding_chunk_tokens
    overlap = settings.embedding_chunk_overlap

    while start < token_count:
        end = min(start + target_size, token_count)
        if end < token_count:
            lower_bound = min(end, start + max(32, target_size // 2))
            sentence_boundaries = []
            for candidate in range(lower_bound, end + 1):
                char_end = offsets[candidate - 1][1]
                has_trailing_space = char_end >= len(text) or text[char_end].isspace()
                if (
                    char_end > 0
                    and text[char_end - 1] in SENTENCE_END
                    and has_trailing_space
                ):
                    sentence_boundaries.append(candidate)
            if sentence_boundaries:
                end = sentence_boundaries[-1]
            else:
                while end > lower_bound:
                    next_char = offsets[end][0]
                    if next_char == 0 or text[next_char - 1].isspace():
                        break
                    end -= 1

        char_start = offsets[start][0]
        char_end = offsets[end - 1][1]
        chunk = text[char_start:char_end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= token_count:
            break

        next_start = max(start + 1, end - overlap)
        while next_start < end:
            next_char = offsets[next_start][0]
            if next_char == 0 or text[next_char - 1].isspace():
                break
            next_start += 1
        start = next_start

    return chunks
