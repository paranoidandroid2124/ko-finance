from __future__ import annotations

import json
from pathlib import Path

import pytest

from services import plan_config_store


def test_plan_config_defaults(monkeypatch: pytest.MonkeyPatch):
    plan_config_store.clear_plan_config_cache()
    monkeypatch.delenv("PLAN_CONFIG_FILE", raising=False)
    config = plan_config_store.get_tier_config("pro")
    assert "search.compare" in config["entitlements"]
    assert "search.export" in config["entitlements"]
    assert "rag.core" in config["entitlements"]
    assert config["quota"]["chatRequestsPerDay"] == 500
    assert config["quota"]["selfCheckEnabled"] is True


def test_plan_config_override_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    payload = {
        "tiers": {
            "pro": {
                "entitlements": ["timeline.full", " search.alerts "],
                "quota": {
                    "chatRequestsPerDay": 999,
                    "ragTopK": "12",
                    "selfCheckEnabled": False,
                    "peerExportRowLimit": "0",
                },
            }
        },
        "updated_by": "tester@kfinance.ai",
    }
    path = tmp_path / "plan_config.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setenv("PLAN_CONFIG_FILE", str(path))
    plan_config_store.clear_plan_config_cache()
    plan_config_store.reload_plan_config()

    config = plan_config_store.get_tier_config("pro")
    assert config["entitlements"] == ["timeline.full", "search.alerts"]
    assert config["quota"]["chatRequestsPerDay"] == 999
    assert config["quota"]["ragTopK"] == 12
    assert config["quota"]["selfCheckEnabled"] is False
    assert config["quota"]["peerExportRowLimit"] == 0


def test_unknown_tier_falls_back_to_free():
    plan_config_store.clear_plan_config_cache()
    config = plan_config_store.get_tier_config("custom-tier")
    # free tier defaults
    assert config["entitlements"] == ["search.alerts"]
    assert config["quota"]["chatRequestsPerDay"] == 20
