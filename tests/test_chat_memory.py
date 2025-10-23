import types
import uuid
from unittest.mock import MagicMock

from llm.prompts import rag_qa, table_aware_rag
from services import chat_service


def test_trim_preview_truncates_long_text():
    text = " ".join(["데모"] * 200)
    preview = chat_service.trim_preview(text)
    assert len(preview) <= chat_service.SUMMARY_PREVIEW_LIMIT
    assert preview.endswith("...")


def test_should_trigger_summary_respects_threshold():
    session = types.SimpleNamespace(id=uuid.uuid4(), memory_snapshot={"summarized_until": 0})
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = chat_service.SUMMARY_TRIGGER_MESSAGES + 2

    assert chat_service.should_trigger_summary(db, session) is True


def test_should_trigger_summary_requires_minimum_pairs():
    session = types.SimpleNamespace(id=uuid.uuid4(), memory_snapshot={"summarized_until": 0})
    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = chat_service.RECENT_TURN_LIMIT * 2

    assert chat_service.should_trigger_summary(db, session) is False


def test_rag_prompt_memory_block_format():
    memory = {
        "summary": "요약 내용",
        "recent_turns": [{"role": "user", "content": "질문"}, {"role": "assistant", "content": "답변"}],
        "citations": ["p.3", "doc-1"],
    }
    prompt = rag_qa.get_prompt("무엇이 중요한가?", [], conversation_memory=memory)
    user_prompt = prompt[1]["content"]
    assert "요약 내용" in user_prompt
    assert "Copilot: 답변" in user_prompt


def test_table_prompt_memory_block_format():
    memory = {
        "summary": "표 기반 요약",
        "recent_turns": [{"role": "assistant", "content": "표 설명"}],
    }
    prompt = table_aware_rag.get_prompt("표 질문", [], conversation_memory=memory)
    user_prompt = prompt[1]["content"]
    assert "표 기반 요약" in user_prompt
    assert "Copilot: 표 설명" in user_prompt

