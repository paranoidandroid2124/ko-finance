import os
import json
from pathlib import Path
from typing import Iterator, Tuple

import importlib
import warnings
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm import guardrails, llm_service
from services import admin_audit, admin_llm_store, admin_ops_service, admin_rag_service, admin_ui_service, vector_service

ADMIN_TOKEN = "test-admin-token"
ADMIN_AUTH_HEADER = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture()
def admin_test_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Tuple[TestClient, Path, Path]]:
    if admin_llm_store.yaml is None:
        pytest.skip("PyYAML is required for LiteLLM profile management tests.")

    admin_dir = tmp_path / "admin"
    admin_dir.mkdir(parents=True, exist_ok=True)

    # Redirect admin storage paths to the temporary directory.
    monkeypatch.setattr(admin_audit, "_AUDIT_DIR", admin_dir, raising=False)
    monkeypatch.setattr(admin_llm_store, "_ADMIN_DIR", admin_dir, raising=False)
    monkeypatch.setattr(admin_llm_store, "_PROMPTS_PATH", admin_dir / "system_prompts.json", raising=False)
    monkeypatch.setattr(admin_llm_store, "_GUARDRAIL_PATH", admin_dir / "guardrails_policy.json", raising=False)

    monkeypatch.setattr(admin_rag_service, "_ADMIN_DIR", admin_dir, raising=False)
    monkeypatch.setattr(admin_rag_service, "_RAG_CONFIG_PATH", admin_dir / "rag_config.json", raising=False)
    monkeypatch.setattr(admin_rag_service, "_RAG_HISTORY_PATH", admin_dir / "rag_reindex.jsonl", raising=False)

    monkeypatch.setattr(admin_ops_service, "_ADMIN_DIR", admin_dir, raising=False)
    monkeypatch.setattr(admin_ops_service, "_OPS_PIPELINE_PATH", admin_dir / "ops_news_pipeline.json", raising=False)
    monkeypatch.setattr(admin_ops_service, "_OPS_API_KEYS_PATH", admin_dir / "ops_api_keys.json", raising=False)
    monkeypatch.setattr(admin_ops_service, "_OPS_RUN_HISTORY_PATH", admin_dir / "ops_run_history.jsonl", raising=False)
    monkeypatch.setattr(
        admin_ops_service,
        "_OPS_ALERT_CHANNELS_PATH",
        admin_dir / "ops_alert_channels.json",
        raising=False,
    )
    monkeypatch.setattr(admin_ui_service, "_ADMIN_DIR", admin_dir, raising=False)
    monkeypatch.setattr(admin_ui_service, "_UI_SETTINGS_PATH", admin_dir / "ui_settings.json", raising=False)

    # Prepare LiteLLM configuration file.
    litellm_config_path = tmp_path / "litellm_config.yaml"
    litellm_config_path.write_text(
        "model_list:\n"
        "  - model_name: base-chat\n"
        "    litellm_params:\n"
        "      model: existing-model\n"
        "      temperature: 0.1\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LITELLM_CONFIG_PATH", str(litellm_config_path))

    # Admin authentication token.
    monkeypatch.setenv("ADMIN_API_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("ADMIN_RAG_AUTO_RETRY_ENABLED", "false")
    monkeypatch.delenv("ADMIN_API_TOKENS", raising=False)

    # Ensure guardrail runtime state is clean.
    guardrails.update_guardrail_blocklist([])
    guardrails.update_safe_message(None)
    llm_service.set_guardrail_copy(None)

    # Avoid hitting an actual Qdrant instance during tests.
    monkeypatch.setattr(vector_service, "init_collection", lambda: None)

    # Reload routers so that patched paths take effect.
    admin_llm_module = importlib.reload(importlib.import_module("web.routers.admin_llm"))
    admin_rag_module = importlib.reload(importlib.import_module("web.routers.admin_rag"))
    admin_ops_module = importlib.reload(importlib.import_module("web.routers.admin_ops"))
    admin_ui_module = importlib.reload(importlib.import_module("web.routers.admin_ui"))

    app = FastAPI()
    app.include_router(admin_llm_module.router, prefix="/api/v1")
    app.include_router(admin_rag_module.router, prefix="/api/v1")
    app.include_router(admin_ops_module.router, prefix="/api/v1")
    app.include_router(admin_ui_module.router, prefix="/api/v1")

    client = TestClient(app)
    try:
        yield client, admin_dir, litellm_config_path
    finally:
        client.close()


def test_llm_profile_and_guardrail_management(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, config_path = admin_test_client

    # List existing profiles.
    response = client.get("/api/v1/admin/llm/profiles", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200, response.text
    assert response.json()["profiles"][0]["model"] == "existing-model"

    # Upsert new profile and ensure YAML is persisted.
    payload = {
        "name": "quality-chat",
        "model": "gpt-5-chat",
        "settings": {"temperature": 0.25, "top_p": 0.8},
        "actor": "qa-admin@kfinance.ai",
        "note": "Add high quality route",
    }
    response = client.put("/api/v1/admin/llm/profiles/quality-chat", json=payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["profile"]["name"] == "quality-chat"
    stored = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    profile_entry = next(
        entry for entry in stored["model_list"] if entry["model_name"] == "quality-chat"
    )
    assert profile_entry["litellm_params"]["model"] == "gpt-5-chat"

    # Update system prompt.
    prompt_payload = {
        "channel": "chat",
        "prompt": "Warm, social-enterprise tone with compliance reminder.",
        "actor": "qa-admin@kfinance.ai",
        "note": "Align with phase4 tone",
    }
    response = client.put("/api/v1/admin/llm/prompts/system", json=prompt_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    prompts_store = json.loads((admin_dir / "system_prompts.json").read_text(encoding="utf-8"))
    assert prompts_store["chat"]["prompt"] == prompt_payload["prompt"]

    # Update guardrail policy and confirm runtime state.
    guardrail_payload = {
        "intentRules": [{"name": "finance_only", "threshold": 0.8}],
        "blocklist": ["pump and dump", "sure win"],
        "userFacingCopy": {
            "fallback": "조금만 기다려 주세요, 안전한 답변을 준비 중이에요!",
            "blocked": "내부 정책상 안내가 어려운 주제입니다.",
        },
        "actor": "qa-admin@kfinance.ai",
        "note": "Tighten investment phrasing guardrail",
    }
    response = client.put("/api/v1/admin/llm/guardrails/policies", json=guardrail_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    assert guardrails.SAFE_MESSAGE == guardrail_payload["userFacingCopy"]["fallback"]

    # Evaluate sample text containing a blocked phrase.
    response = client.post(
        "/api/v1/admin/llm/guardrails/evaluate",
        json={"sample": "이건 pump and dump 전략이에요.", "channels": ["chat"]},
        headers=ADMIN_AUTH_HEADER,
    )
    with warnings.catch_warnings(record=True) as collected:
        warnings.simplefilter("always")
        assert response.status_code == 200
        body = response.json()
    assert not collected, f"Pydantic guardrail warnings: {[str(item.message) for item in collected]}"
    assert body["result"] == "blocked"
    assert "pump and dump" in body["details"]["matchedRules"][0]

    # Audit log should capture profile update.
    audit_lines = (admin_dir / "llm_audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert any("profile_upsert" in line for line in audit_lines)


def test_rag_config_and_reindex_history(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    response = client.get("/api/v1/admin/rag/config", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    assert response.json()["config"]["similarityThreshold"] == pytest.approx(0.62, rel=1e-5)

    update_payload = {
        "sources": [
            {"key": "filings", "name": "공시", "enabled": True, "metadata": {}},
            {"key": "news", "name": "뉴스", "enabled": False, "metadata": {}},
        ],
        "filters": [{"field": "sector", "operator": "in", "value": ["금융"]}],
        "similarityThreshold": 0.7,
        "rerankModel": "custom-reranker",
        "actor": "qa-admin@kfinance.ai",
        "note": "Adjust RAG defaults for pilot",
    }
    response = client.put("/api/v1/admin/rag/config", json=update_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    stored = json.loads((admin_dir / "rag_config.json").read_text(encoding="utf-8"))
    assert stored["rerankModel"] == "custom-reranker"
    assert stored["filters"][0]["field"] == "sector"

    reindex_payload = {"sources": ["filings"], "refreshFilters": False, "actor": "qa-admin@kfinance.ai", "note": "QA run"}
    response = client.post("/api/v1/admin/rag/reindex", json=reindex_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    result_body = response.json()
    assert result_body["status"] == "completed"
    task_id = result_body["taskId"]

    history_lines = (admin_dir / "rag_reindex.jsonl").read_text(encoding="utf-8").splitlines()
    statuses = [json.loads(line)["status"] for line in history_lines]
    assert statuses[-3:] == ["queued", "running", "completed"]

    history_response = client.get("/api/v1/admin/rag/reindex/history", headers=ADMIN_AUTH_HEADER)
    assert history_response.status_code == 200
    history_payload = history_response.json()
    runs = history_payload["runs"]
    assert len(runs) >= 3
    assert any(entry["taskId"] == task_id for entry in runs)
    latest_entry = runs[0]
    assert latest_entry["taskId"] == task_id
    assert latest_entry["status"] == "completed"
    assert latest_entry["startedAt"] is not None
    assert latest_entry["finishedAt"] is not None
    assert isinstance(latest_entry["durationMs"], int)
    assert latest_entry["langfuseTraceUrl"] in (None, "")
    assert latest_entry.get("retryMode") == "manual"
    assert isinstance(latest_entry.get("scopeDetail"), list)
    diff_payload = latest_entry.get("evidenceDiff")
    assert isinstance(diff_payload, dict)
    assert "totalChanges" in diff_payload
    assert latest_entry.get("ragMode") == "vector"
    assert runs[1]["status"] == "running"
    assert runs[2]["status"] == "queued"


def test_rag_opt_gap(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    admin_rag_service.append_reindex_history(
        task_id="rag-opt-001",
        actor="judge-optional",
        scope="filings",
        status="completed",
        note="judge optional flow",
        retry_mode="manual",
        rag_mode="optional",
        scope_detail=["filings"],
        langfuse_trace_url="https://langfuse.local/trace-opt",
        langfuse_trace_id="trace-opt",
        evidence_diff={"totalChanges": 0, "created": 0, "updated": 0, "removed": 0, "samples": []},
    )
    admin_rag_service.append_reindex_history(
        task_id="rag-none-001",
        actor="judge-none",
        scope="all",
        status="completed",
        note="judge none fallback",
        rag_mode="none",
        error_code=None,
    )

    response = client.get("/api/v1/admin/rag/reindex/history", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert len(runs) >= 2

    latest = runs[0]
    assert latest["taskId"] == "rag-none-001"
    assert latest["ragMode"] == "none"
    assert latest["retryMode"] is None
    assert latest["scopeDetail"] is None

    optional_entry = next(item for item in runs if item["taskId"] == "rag-opt-001")
    assert optional_entry["ragMode"] == "optional"
    assert optional_entry["retryMode"] == "manual"
    assert optional_entry["scopeDetail"] == ["filings"]
    assert optional_entry["langfuseTraceUrl"] == "https://langfuse.local/trace-opt"


def test_ops_pipeline_schedule_and_run_history(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    # Schedules should reflect Celery beat configuration.
    response = client.get("/api/v1/admin/ops/schedules", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    schedules = response.json()["jobs"]
    assert len(schedules) > 0
    first_job = schedules[0]["id"]

    # Update news pipeline and ensure persistence + environment variable.
    news_payload = {
        "rssFeeds": ["https://example.com/rss"],
        "sectorMappings": {"금융": ["은행"]},
        "sentiment": {"threshold": 0.6},
        "actor": "qa-admin@kfinance.ai",
        "note": "Focus on 금융",
    }
    response = client.put("/api/v1/admin/ops/news-pipeline", json=news_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    stored = json.loads((admin_dir / "ops_news_pipeline.json").read_text(encoding="utf-8"))
    assert stored["rssFeeds"] == news_payload["rssFeeds"]
    assert os.environ["NEWS_FEEDS"] == "https://example.com/rss"

    # Update API keys.
    key_payload = {
        "langfuse": {
            "enabled": True,
            "environment": "staging",
            "apiKey": "ls-****",
            "expiresAt": "2025-01-01T00:00:00Z",
            "warningThresholdDays": 14,
        },
        "externalApis": [
            {
                "name": "openai",
                "maskedKey": "sk-****",
                "enabled": True,
                "metadata": {},
                "expiresAt": "2025-06-01T00:00:00Z",
                "warningThresholdDays": 30,
            },
        ],
        "actor": "qa-admin@kfinance.ai",
        "note": "Rotate OpenAI key",
    }
    response = client.put("/api/v1/admin/ops/api-keys", json=key_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    stored_keys = json.loads((admin_dir / "ops_api_keys.json").read_text(encoding="utf-8"))
    assert stored_keys["externalApis"][0]["name"] == "openai"
    assert stored_keys["langfuse"]["warningThresholdDays"] == 14
    assert stored_keys["langfuse"]["expiresAt"].startswith("2025-01-01")
    assert stored_keys["externalApis"][0]["warningThresholdDays"] == 30

    # Trigger a schedule and ensure run history records the request.
    trigger_payload = {"actor": "qa-admin@kfinance.ai", "note": "Manual trigger"}
    response = client.post(f"/api/v1/admin/ops/schedules/{first_job}/trigger", json=trigger_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    task_id = response.json()["taskId"]
    history_response = client.get("/api/v1/admin/ops/run-history", headers=ADMIN_AUTH_HEADER)
    assert history_response.status_code == 200
    history_items = history_response.json()["runs"]
    assert any(run["id"] == task_id for run in history_items)

    # Update alert channels.
    channel_payload = {
        "channels": [
            {
                "key": "telegram-primary",
                "label": "텔레그램 운영 채널",
                "channelType": "telegram",
                "enabled": True,
                "targets": ["-100123456"],
                "metadata": {"thread": "ops"},
                "template": "default",
                "messageTemplate": "{message}",
            }
        ],
        "actor": "qa-admin@kfinance.ai",
        "note": "Register telegram channel",
    }
    response = client.put("/api/v1/admin/ops/alert-channels", json=channel_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    stored_channels = json.loads((admin_dir / "ops_alert_channels.json").read_text(encoding="utf-8"))
    assert stored_channels["channels"][0]["channelType"] == "telegram"

    channels_response = client.get("/api/v1/admin/ops/alert-channels", headers=ADMIN_AUTH_HEADER)
    assert channels_response.status_code == 200
    payload = channels_response.json()
    assert payload["channels"][0]["label"] == "텔레그램 운영 채널"



def test_alert_channel_audit_aggregation(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    create_payload = {
        "channelType": "telegram",
        "label": "운영 알림",
        "targets": ["-100987"],
        "metadata": {"thread": "ops"},
        "template": "default",
        "messageTemplate": "[알림] {message}",
        "description": "테스트 채널",
        "actor": "qa-admin@kfinance.ai",
        "note": "채널 생성",
    }
    response = client.post(
        "/api/v1/admin/ops/alert-channels",
        json=create_payload,
        headers=ADMIN_AUTH_HEADER,
    )
    assert response.status_code == 201
    stored = json.loads((admin_dir / "ops_alert_channels.json").read_text(encoding="utf-8"))
    assert stored["channels"][0]["label"] == "운영 알림"
    channel_key = stored["channels"][0]["key"]

    disable_payload = {"enabled": False, "actor": "qa-admin@kfinance.ai", "note": "점검"}
    response = client.patch(
        f"/api/v1/admin/ops/alert-channels/{channel_key}/status",
        json=disable_payload,
        headers=ADMIN_AUTH_HEADER,
    )
    assert response.status_code == 200

    enable_payload = {"enabled": True, "actor": "qa-admin@kfinance.ai", "note": "복구"}
    response = client.patch(
        f"/api/v1/admin/ops/alert-channels/{channel_key}/status",
        json=enable_payload,
        headers=ADMIN_AUTH_HEADER,
    )
    assert response.status_code == 200

    audit_response = client.get(
        "/api/v1/admin/ops/audit/logs",
        params={"source": "alerts_audit.jsonl", "limit": 20},
        headers=ADMIN_AUTH_HEADER,
    )
    assert audit_response.status_code == 200
    audit_items = audit_response.json()["items"]
    assert any(entry["action"] == "alert_channel_create" for entry in audit_items)
    assert any(entry["action"] == "alert_channel_status" for entry in audit_items)
def test_langfuse_audit_rotation_history(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    rotate_payload = {"actor": "qa-admin@kfinance.ai", "note": "자동 회전"}
    response = client.post(
        "/api/v1/admin/ops/api-keys/langfuse/rotate",
        json=rotate_payload,
        headers=ADMIN_AUTH_HEADER,
    )
    assert response.status_code == 200
    stored = json.loads((admin_dir / "ops_api_keys.json").read_text(encoding="utf-8"))
    history = stored["langfuse"].get("rotationHistory")
    assert history
    assert history[0]["actor"] == "qa-admin@kfinance.ai"

    audit_response = client.get(
        "/api/v1/admin/ops/audit/logs",
        params={"source": "ops_audit.jsonl", "action": "langfuse_rotate", "limit": 10},
        headers=ADMIN_AUTH_HEADER,
    )
    assert audit_response.status_code == 200
    audit_items = audit_response.json()["items"]
    assert audit_items
def test_ui_ux_settings_management(admin_test_client: Tuple[TestClient, Path, Path]) -> None:
    client, admin_dir, _ = admin_test_client

    response = client.get("/api/v1/admin/ui/settings", headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["theme"]["primaryColor"].startswith("#")

    update_payload = {
        "settings": {
            "theme": {"primaryColor": "#0F172A", "accentColor": "#F97316"},
            "defaults": {"dateRange": "3M", "landingView": "alerts"},
            "copy": {
                "welcomeHeadline": "같이 누적 데이터를 살펴볼 준비가 됐어요.",
                "welcomeSubcopy": "지금도 투자자에게 안전한 가이드를 전하고 있어요.",
                "quickCta": "RAG 근거 모으기",
            },
            "banner": {
                "enabled": True,
                "message": "신규 기능 실험을 곧 시작해요. 관심 있다면 팀에 알려 주세요!",
                "linkLabel": "실험 일정 보기",
                "linkUrl": "https://kfinance.ai/experiments",
            },
        },
        "actor": "qa-admin@kfinance.ai",
        "note": "UI 배너 실험 공지",
    }
    response = client.put("/api/v1/admin/ui/settings", json=update_payload, headers=ADMIN_AUTH_HEADER)
    assert response.status_code == 200
    persisted = json.loads((admin_dir / "ui_settings.json").read_text(encoding="utf-8"))
    assert persisted["theme"]["primaryColor"] == "#0F172A"
    assert persisted["defaults"]["landingView"] == "alerts"
    assert persisted["banner"]["enabled"] is True


