from uuid import uuid4

import pytest

from app.services.evaluation import benchmark_retrieval, mean_retrieval_metrics, retrieval_metrics


def test_retrieval_metrics_compute_recall_at_k_and_reciprocal_rank() -> None:
    relevant_a, relevant_b, distractor = uuid4(), uuid4(), uuid4()

    metrics = retrieval_metrics(
        {relevant_a, relevant_b},
        [distractor, relevant_a, relevant_b],
        k=2,
    )

    assert metrics == {"recall_at_k": 0.5, "reciprocal_rank": 0.5}


def test_mean_metrics_average_queries_and_reject_empty_benchmarks() -> None:
    first, second, unrelated = uuid4(), uuid4(), uuid4()

    metrics = mean_retrieval_metrics([({first}, [first]), ({second}, [unrelated])], k=1)

    assert metrics == {"queries": 2.0, "recall_at_k": 0.5, "mrr": 0.5, "k": 1.0}
    with pytest.raises(ValueError, match="At least one labeled query"):
        mean_retrieval_metrics([])


def test_retrieval_metrics_require_labeled_relevance() -> None:
    with pytest.raises(ValueError, match="relevant chunk ID"):
        retrieval_metrics([], [], k=5)


def test_benchmark_reports_retrieval_quality_and_latency() -> None:
    workspace_id = uuid4()
    first, second, distractor = uuid4(), uuid4(), uuid4()
    cases = [(workspace_id, "first query", [first]), (workspace_id, "second query", [second])]

    metrics = benchmark_retrieval(
        cases,
        lambda _workspace, query: [first] if query == "first query" else [distractor, second],
        k=2,
    )

    assert metrics["queries"] == 2
    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr"] == 0.75
    assert metrics["mean_latency_ms"] >= 0
    assert metrics["p50_latency_ms"] >= 0
    assert metrics["p95_latency_ms"] >= 0
