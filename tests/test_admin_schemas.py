import pytest
from pydantic import ValidationError

from schemas.api.admin import (
    AdminLlmProfileSchema,
    AdminOpsAlertChannelSchema,
    AdminRagReindexRecordSchema,
)


def test_admin_llm_profile_forbids_extra_fields() -> None:
    payload = {
        "name": "quality-chat",
        "model": "gpt-5-chat",
        "settings": {"temperature": 0.2, "top_p": 0.9},
    }
    profile = AdminLlmProfileSchema.model_validate(payload)
    assert profile.settings["temperature"] == 0.2

    with pytest.raises(ValidationError):
        AdminLlmProfileSchema.model_validate({**payload, "unexpected": True})


def test_admin_ops_alert_channel_normalization() -> None:
    payload = {
        "key": "telegram-primary",
        "label": "텔레그램 운영 채널",
        "channelType": "telegram",
        "enabled": True,
        "targets": [" -100123456 ", " -100123456 ", "\n-100987654"],
        "metadata": {"scope": {"type": "ops"}, "": "ignore"},
    }
    channel = AdminOpsAlertChannelSchema.model_validate(payload)

    assert channel.targets == ["-100123456", "-100987654"]
    assert channel.metadata == {"scope": {"type": "ops"}}

    with pytest.raises(ValidationError):
        AdminOpsAlertChannelSchema.model_validate({**payload, "extraField": "not-allowed"})


def test_admin_rag_reindex_record_requires_known_fields() -> None:
    payload = {
        "taskId": "rag-task-123",
        "actor": "qa-admin@kfinance.ai",
        "scope": "filings,news",
        "status": "completed",
        "timestamp": "2025-10-31T09:00:00+00:00",
        "retryMode": "manual",
        "ragMode": "optional",
        "scopeDetail": ["filings", "news"],
    }
    record = AdminRagReindexRecordSchema.model_validate(payload)
    assert record.scopeDetail == ["filings", "news"]
    assert record.retryMode == "manual"

    with pytest.raises(ValidationError):
        AdminRagReindexRecordSchema.model_validate({**payload, "preview": "not-expected"})
