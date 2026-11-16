import pytest
from pydantic import ValidationError

from app.schemas.conversation import QuestionCreate
from app.schemas.search import SearchRequest


def test_question_text_is_trimmed() -> None:
    assert QuestionCreate(content="  Where is the policy?  ").content == "Where is the policy?"


@pytest.mark.parametrize("content", ["", "   ", "x"])
def test_question_rejects_blank_or_too_short_text(content: str) -> None:
    with pytest.raises(ValidationError):
        QuestionCreate(content=content)


def test_search_request_enforces_limit_and_nonblank_query() -> None:
    assert SearchRequest(query="  leave policy  ").query == "leave policy"
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")
    with pytest.raises(ValidationError):
        SearchRequest(query="leave policy", limit=21)
