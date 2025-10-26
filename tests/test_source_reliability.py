import json
from collections import Counter

from services.reliability.source_reliability import (
    apply_window_penalties,
    average_reliability,
    reset_override_cache,
    score_article,
)


def test_score_article_known_domain():
    score = score_article("연합뉴스", "https://www.yonhapnews.co.kr/market/article123")
    assert 0.0 <= score <= 1.0
    assert score >= 0.9  # Yonhap baseline


def test_score_article_unknown_domain_defaults():
    score = score_article("블로그", "https://unknown.example.com/post")
    assert score == 0.4  # default fallback


def test_average_reliability_filters_none():
    assert average_reliability([0.8, None, 0.6]) == 0.7
    assert average_reliability([None, None]) is None


def test_domain_override_from_file(tmp_path, monkeypatch):
    override = {"domains": {"unknown.example.com": 0.55}}
    override_path = tmp_path / "overrides.json"
    override_path.write_text(json.dumps(override), encoding="utf-8")

    monkeypatch.setenv("SOURCE_RELIABILITY_OVERRIDE_PATH", str(override_path))
    monkeypatch.delenv("SOURCE_RELIABILITY_OVERRIDES_JSON", raising=False)
    reset_override_cache()

    score = score_article("블로그", "https://unknown.example.com/post")
    assert score == 0.55

    monkeypatch.delenv("SOURCE_RELIABILITY_OVERRIDE_PATH", raising=False)
    reset_override_cache()


def test_volume_penalty_via_overrides(monkeypatch):
    monkeypatch.setenv(
        "SOURCE_RELIABILITY_OVERRIDES_JSON",
        json.dumps({"penalties": {"volume_threshold": 2, "volume_penalty_step": 0.05, "volume_max_penalty": 0.1}}),
    )
    reset_override_cache()

    adjusted = apply_window_penalties(0.9, Counter({"example.com": 5}))
    assert adjusted < 0.9

    monkeypatch.delenv("SOURCE_RELIABILITY_OVERRIDES_JSON", raising=False)
    reset_override_cache()
