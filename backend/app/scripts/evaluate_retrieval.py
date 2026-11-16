"""Run an offline labeled retrieval benchmark against the configured database."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.evaluation import benchmark_retrieval
from app.services.rag import retrieve_evidence


def load_dataset(path: Path) -> list[tuple[UUID, str, list[UUID]]]:
    cases = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            query = row["query"]
            relevant_ids = row["relevant_chunk_ids"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be a non-empty string")
            if not isinstance(relevant_ids, list) or not relevant_ids:
                raise ValueError("relevant_chunk_ids must be a non-empty array")
            cases.append(
                (
                    UUID(row["workspace_id"]),
                    query.strip(),
                    [UUID(value) for value in relevant_ids],
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid benchmark data on line {line_number}.") from exc
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset", type=Path, help="Private JSONL file of labeled workspace queries"
    )
    parser.add_argument("--top-k", type=int, default=settings.rag_top_k)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    cases = load_dataset(args.dataset)

    with SessionLocal() as db:
        metrics = benchmark_retrieval(
            cases,
            lambda workspace_id, query: _retrieve_ids(db, workspace_id, query, args.top_k),
            k=args.top_k,
        )
    print(json.dumps(metrics, indent=2))


def _retrieve_ids(db: Session, workspace_id: UUID, query: str, limit: int) -> list[UUID]:
    return [item["chunk"].id for item in retrieve_evidence(db, workspace_id, query, limit=limit)]


if __name__ == "__main__":
    main()
