from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from services.plan_catalog_service import load_plan_catalog, update_plan_catalog


def _read_catalog_file(path: Path) -> Dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def catalog_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "plan_catalog.json"
    monkeypatch.setenv("PLAN_CATALOG_FILE", str(target))
    return target


def test_load_plan_catalog_defaults(catalog_env: Path) -> None:
    payload = load_plan_catalog(reload=True)
    tiers = payload["tiers"]
    assert len(tiers) == 3
    assert {tier["tier"] for tier in tiers} == {"free", "pro", "enterprise"}
    assert payload["updated_at"] is None


def test_update_plan_catalog_persists(catalog_env: Path) -> None:
    updated = update_plan_catalog(
        [
            {
                "tier": "free",
                "title": "무료",
                "tagline": "체험용",
                "price": {"amount": 0, "currency": "KRW", "interval": "월"},
                "ctaLabel": "시작",
                "ctaHref": "/start",
                "features": [{"text": "챗 10회"}],
            }
        ],
        updated_by="tester@kfinance.ai",
        note="단일 플랜 테스트",
    )

    assert updated["updated_by"] == "tester@kfinance.ai"
    assert updated["note"] == "단일 플랜 테스트"

    raw = _read_catalog_file(catalog_env)
    assert raw["updated_by"] == "tester@kfinance.ai"
    assert raw["tiers"][0]["tier"] == "free"
    assert raw["tiers"][0]["features"][0]["text"] == "챗 10회"
