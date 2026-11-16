import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.services.rag import AnswerProviderError, generate_answer


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_provider_answer_only_accepts_citations_from_retrieved_evidence(monkeypatch) -> None:
    allowed_id, unrelated_id = uuid4(), uuid4()
    captured = {}
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("fake-test-key"))
    monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com/v1")

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "answer": "Employees receive 12 days.",
                                    "cited_chunk_ids": [str(allowed_id), str(unrelated_id)],
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.services.rag.httpx.post", fake_post)
    evidence = [
        {
            "chunk": SimpleNamespace(id=allowed_id, content="Employees receive 12 days."),
            "document": SimpleNamespace(filename="Policy.pdf"),
            "page": SimpleNamespace(page_number=4),
            "score": 0.81,
        }
    ]

    answer, cited_ids = generate_answer(
        "How many days?", evidence, [{"role": "user", "content": "Earlier question"}]
    )

    assert answer == "Employees receive 12 days."
    assert cited_ids == [allowed_id]
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer fake-test-key"
    request_messages = captured["json"]["messages"]
    assert "untrusted data" in request_messages[0]["content"]
    supplied_evidence = json.loads(request_messages[-1]["content"])["evidence"]
    assert supplied_evidence[0]["chunk_id"] == str(allowed_id)


def test_provider_is_not_called_without_a_configured_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("  "))
    monkeypatch.setattr(
        "app.services.rag.httpx.post",
        lambda *_args, **_kwargs: pytest.fail("Provider must not be called without a key."),
    )

    with pytest.raises(AnswerProviderError, match="LLM_API_KEY"):
        generate_answer("Question?", [], [])


def test_malformed_provider_citation_is_reported_as_provider_error(monkeypatch) -> None:
    chunk_id = uuid4()
    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_api_key", SecretStr("fake-test-key"))
    monkeypatch.setattr(
        "app.services.rag.httpx.post",
        lambda *_args, **_kwargs: FakeResponse(
            {"choices": [{"message": {"content": '{"answer":"Answer","cited_chunk_ids":["bad"]}'}}]}
        ),
    )
    evidence = [
        {
            "chunk": SimpleNamespace(id=chunk_id, content="Evidence"),
            "document": SimpleNamespace(filename="Policy.pdf"),
            "page": SimpleNamespace(page_number=1),
            "score": 0.9,
        }
    ]

    with pytest.raises(AnswerProviderError, match="valid response"):
        generate_answer("Question?", evidence, [])
