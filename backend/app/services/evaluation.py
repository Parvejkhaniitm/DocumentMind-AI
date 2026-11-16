from collections.abc import Callable, Iterable, Sequence
from math import ceil
from time import perf_counter
from uuid import UUID


def retrieval_metrics(
    relevant_chunk_ids: Iterable[UUID],
    retrieved_chunk_ids: Sequence[UUID],
    *,
    k: int = 10,
) -> dict[str, float]:
    """Return recall@k and reciprocal rank for one labeled retrieval query."""
    relevant = set(relevant_chunk_ids)
    if not relevant:
        raise ValueError("At least one relevant chunk ID is required for evaluation.")
    if k < 1:
        raise ValueError("k must be at least 1.")

    ranked = retrieved_chunk_ids[:k]
    recall = len(relevant.intersection(ranked)) / len(relevant)
    reciprocal_rank = next(
        (1.0 / rank for rank, chunk_id in enumerate(ranked, start=1) if chunk_id in relevant),
        0.0,
    )
    return {"recall_at_k": recall, "reciprocal_rank": reciprocal_rank}


def mean_retrieval_metrics(
    cases: Iterable[tuple[Iterable[UUID], Sequence[UUID]]], *, k: int = 10
) -> dict[str, float | int]:
    """Average query-level recall@k and MRR over a fixed relevance set."""
    scores = [retrieval_metrics(relevant, retrieved, k=k) for relevant, retrieved in cases]
    if not scores:
        raise ValueError("At least one labeled query is required for evaluation.")
    return {
        "queries": len(scores),
        "recall_at_k": sum(score["recall_at_k"] for score in scores) / len(scores),
        "mrr": sum(score["reciprocal_rank"] for score in scores) / len(scores),
        "k": k,
    }


def benchmark_retrieval(
    cases: Iterable[tuple[UUID, str, Iterable[UUID]]],
    retrieve: Callable[[UUID, str], Sequence[UUID]],
    *,
    k: int = 10,
) -> dict[str, float | int]:
    """Measure retrieval quality and elapsed query latency for a labeled dataset."""
    scores = []
    latencies_ms = []
    for workspace_id, query, relevant_ids in cases:
        started = perf_counter()
        retrieved_ids = retrieve(workspace_id, query)
        latencies_ms.append((perf_counter() - started) * 1000)
        scores.append(retrieval_metrics(relevant_ids, retrieved_ids, k=k))

    if not scores:
        raise ValueError("At least one labeled query is required for evaluation.")
    ranked_latencies = sorted(latencies_ms)
    return {
        "queries": len(scores),
        "k": k,
        "recall_at_k": sum(score["recall_at_k"] for score in scores) / len(scores),
        "mrr": sum(score["reciprocal_rank"] for score in scores) / len(scores),
        "mean_latency_ms": sum(latencies_ms) / len(latencies_ms),
        "p50_latency_ms": ranked_latencies[ceil(0.50 * len(ranked_latencies)) - 1],
        "p95_latency_ms": ranked_latencies[ceil(0.95 * len(ranked_latencies)) - 1],
    }
