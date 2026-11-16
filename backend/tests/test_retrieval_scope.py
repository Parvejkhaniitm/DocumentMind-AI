from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.services import rag


class CapturingSession:
    statement = None

    def execute(self, statement):
        self.statement = statement
        return []


def test_retrieval_query_is_restricted_to_workspace_and_ready_documents(monkeypatch) -> None:
    workspace_id = uuid4()
    db = CapturingSession()
    monkeypatch.setattr(rag, "embed_query", lambda _query: [0.0] * 384)

    assert rag.retrieve_evidence(db, workspace_id, "policy question") == []

    compiled = db.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "chunks.workspace_id" in sql
    assert "documents.workspace_id" in sql
    assert "documents.status" in sql
    assert str(workspace_id) in [str(value) for value in compiled.params.values()]
