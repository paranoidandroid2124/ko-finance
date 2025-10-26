"""Heuristic helpers for estimating news source reliability with overrides."""

from __future__ import annotations

import json
import os
import threading
from collections import Counter
from typing import Optional
from urllib.parse import urlparse

# Baseline scores tuned manually per high-signal domains.
BASELINE_DOMAIN_SCORES: dict[str, float] = {
    # ── 규제/공식 데이터 (최상단 신뢰)
    "moef.go.kr": 0.97,   # 기재부
    "fsc.go.kr": 0.97,    # 금융위원회 (정책/보도자료)
    "bok.or.kr": 0.98,    # 한국은행 (ECOS/보도) 
    "kosis.kr": 0.97,     # 국가통계포털 KOSIS
    "kostat.go.kr": 0.96, # 통계청
    "ksd.or.kr": 0.96,    # 한국예탁결제원
    "kofia.or.kr": 0.94,  # 금융투자협회
    "kdic.or.kr": 0.96,   # 예금보험공사
    "ftc.go.kr": 0.95,    # 공정거래위원회

    # ── 자본시장 특화(딜/M&A/IB)
    "thebell.co.kr": 0.90,        # 자본시장 특화
    "investchosun.com": 0.89,     # 캐피탈마켓 전문

    # ── 경제 전문지 / 통신
    "asiae.co.kr": 0.80,          # 아시아경제(경제 전문)
    "news1.kr": 0.82,             # 민영 뉴스통신(경제면 강함)
    "newspim.com": 0.80,          # 경제통신
    "etoday.co.kr": 0.78,         # 이투데이
    "newstomato.com": 0.78,       # 뉴스토마토
    "moneys.co.kr": 0.78,         # 머니S
    "seoulfn.com": 0.79,          # 서울파이낸스
    "infostockdaily.co.kr": 0.77, # 인포스탁데일리
    "ajunews.com": 0.79,          # 아주경제

    # ── 방송·경제채널(시황·속보)
    "biz.sbs.co.kr": 0.81,  # SBS Biz
    "ytn.co.kr": 0.82,      # YTN (YTN Biz 포함)
    "mbn.co.kr": 0.79,      # MBN(매일경제TV)

    # ── 국내 영문 경제 매체(해외 인용 용이)
    "kedglobal.com": 0.86,      # 한경 글로벌
    "pulse.mk.co.kr": 0.85,     # 매경 영문
    "koreaherald.com": 0.80,    # 코리아헤럴드(비즈면)
    "koreatimes.co.kr": 0.79,   # 코리아타임스(비즈면)
    "koreajoongangdaily.joins.com": 0.79, # 중앙 영문
    "businesskorea.co.kr": 0.79  # BusinessKorea(월간/영문)
}

# Source name hints (fallback when domain based mapping is unavailable).
BASELINE_SOURCE_SCORES: dict[str, float] = {
    # ── 규제/공식(보도자료 원천) ──
    "기획재정부": 0.97,
    "금융위원회": 0.97,
    "금융감독원": 0.96,
    "한국은행": 0.98,
    "한국거래소": 0.95,
    "예탁결제원": 0.96,
    "금융투자협회": 0.94,
    "공정거래위원회": 0.95,
    "통계청": 0.96,
    "국가통계포털": 0.97,   # KOSIS
    "산업통상자원부": 0.93,
    "중소벤처기업부": 0.92,
    "국토교통부": 0.92,

    # ── 국내 경제/금융 전문지 ──
    "조선비즈": 0.82,
    "이데일리": 0.80,
    "헤럴드경제": 0.80,
    "아시아경제": 0.80,
    "서울파이낸스": 0.79,
    "이투데이": 0.78,
    "뉴스토마토": 0.78,
    "머니S": 0.78,
    "인포스탁데일리": 0.77,

    # ── 통신/와이어 ──
    "연합인포맥스": 0.91,
    "AP통신": 0.87,
    "AFP통신": 0.86,
    "다우존스": 0.86,            # Dow Jones Newswires
    "니케이아시아": 0.84,       # Nikkei Asia

    # ── 자본시장 특화 ──
    "더벨": 0.90,
    "인베스트조선": 0.89,

    # ── 방송/경제채널 ──
    "SBS Biz": 0.81,
    "한국경제TV": 0.82,
    "YTN Biz": 0.82,
    "MBN": 0.79,
    "MTN": 0.80,                 # 머니투데이방송

    # ── 국내 영문 경제 매체 ──
    "KED Global": 0.86,
    "Pulse": 0.85,               # Pulse by Maeil
    "코리아헤럴드": 0.80,
    "코리아타임스": 0.79,
    "중앙데일리": 0.79,
    "비즈니스코리아": 0.79,

    # ── 해외 주요지(이름 기반; 도메인 매칭 없을 때) ──
    "월스트리트저널": 0.88,
    "파이낸셜타임스": 0.88,
    "CNBC": 0.85,

    # ── 산업/테크 특화(경제 이슈 교차 보도) ──
    "지디넷코리아": 0.78,
    "디지털데일리": 0.77,
    "블로터": 0.75,
}

UNKNOWN_SOURCE_PENALTY = 0.4

_override_lock = threading.Lock()
_override_cache: dict[str, object] = {
    "path_mtime": None,
    "path_data": {"domains": {}, "sources": {}, "penalties": {}},
    "env_value": None,
    "env_data": {"domains": {}, "sources": {}, "penalties": {}},
}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, round(value, 3)))


def _empty_overrides() -> dict[str, dict]:
    return {"domains": {}, "sources": {}, "penalties": {}}


def normalize_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if not netloc:
        return None
    netloc = netloc.split("@", 1)[-1]
    if ":" in netloc:
        netloc = netloc.split(":", 1)[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def _score_from_domain(domain: Optional[str]) -> Optional[float]:
    if not domain:
        return None
    if domain in BASELINE_DOMAIN_SCORES:
        return BASELINE_DOMAIN_SCORES[domain]
    if domain.endswith(".go.kr") or domain.endswith(".gov") or ".go.kr" in domain:
        return 0.93
    if domain.endswith(".or.kr"):
        return 0.82
    if domain.endswith(".co.kr") or domain.endswith(".kr"):
        return 0.72
    if domain.endswith(".com"):
        return 0.68
    return None


def _score_from_source_name(source: Optional[str]) -> Optional[float]:
    if not source:
        return None
    normalized = source.strip().lower()
    if not normalized:
        return None
    for key, value in BASELINE_SOURCE_SCORES.items():
        if key.lower() in normalized:
            return value
    return None


def _normalize_override_value(value: object) -> Optional[float]:
    if isinstance(value, (int, float)):
        score = float(value)
        if 0.0 <= score <= 1.0:
            return score
    return None


def _sanitize_overrides(raw: object) -> dict[str, dict]:
    result = _empty_overrides()
    if not isinstance(raw, dict):
        return result

    domains = raw.get("domains", {})
    if isinstance(domains, dict):
        for key, value in domains.items():
            if not isinstance(key, str):
                continue
            score = _normalize_override_value(value)
            if score is not None:
                result["domains"][key.strip().lower()] = score

    sources = raw.get("sources", {})
    if isinstance(sources, dict):
        for key, value in sources.items():
            if not isinstance(key, str):
                continue
            score = _normalize_override_value(value)
            if score is not None:
                result["sources"][key.strip().lower()] = score

    penalties = raw.get("penalties", {})
    if isinstance(penalties, dict):
        result["penalties"] = penalties

    return result


def _merge_overrides(base: dict[str, dict], update: dict[str, dict]) -> dict[str, dict]:
    merged = {
        "domains": dict(base.get("domains", {})),
        "sources": dict(base.get("sources", {})),
        "penalties": dict(base.get("penalties", {})),
    }
    merged["domains"].update(update.get("domains", {}))
    merged["sources"].update(update.get("sources", {}))
    merged["penalties"].update(update.get("penalties", {}))
    return merged


def _load_overrides_from_path(path: str) -> dict[str, dict]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _empty_overrides()
    return _sanitize_overrides(data)


def _load_overrides_from_env(env_value: str) -> dict[str, dict]:
    try:
        data = json.loads(env_value)
    except json.JSONDecodeError:
        return _empty_overrides()
    return _sanitize_overrides(data)


def _get_overrides() -> dict[str, dict]:
    with _override_lock:
        overrides = _empty_overrides()

        path = os.getenv("SOURCE_RELIABILITY_OVERRIDE_PATH")
        if path:
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                mtime = None
            if mtime is not None and mtime != _override_cache.get("path_mtime"):
                _override_cache["path_data"] = _load_overrides_from_path(path)
                _override_cache["path_mtime"] = mtime
            overrides = _merge_overrides(overrides, _override_cache.get("path_data", _empty_overrides()))

        env_json = os.getenv("SOURCE_RELIABILITY_OVERRIDES_JSON")
        if env_json:
            if env_json != _override_cache.get("env_value"):
                _override_cache["env_data"] = _load_overrides_from_env(env_json)
                _override_cache["env_value"] = env_json
            overrides = _merge_overrides(overrides, _override_cache.get("env_data", _empty_overrides()))

        return overrides


def reset_override_cache() -> None:
    with _override_lock:
        _override_cache["path_mtime"] = None
        _override_cache["path_data"] = _empty_overrides()
        _override_cache["env_value"] = None
        _override_cache["env_data"] = _empty_overrides()


def score_article(source: Optional[str], url: Optional[str]) -> float:
    """Return a heuristic reliability score for a news article (0.0 ~ 1.0)."""
    scores: list[float] = []

    domain = normalize_domain(url)
    domain_score = _score_from_domain(domain)
    if domain_score is not None:
        scores.append(domain_score)

    source_score = _score_from_source_name(source)
    if source_score is not None:
        scores.append(source_score)

    base_score = UNKNOWN_SOURCE_PENALTY
    if scores:
        base_score = sum(scores) / len(scores)

    overrides = _get_overrides()
    override_score = None
    if domain:
        override_score = overrides.get("domains", {}).get(domain)
    if override_score is None and source:
        override_score = overrides.get("sources", {}).get(source.strip().lower())
    if override_score is not None:
        base_score = override_score

    return _clamp(base_score)


def apply_window_penalties(score: Optional[float], domain_counts: Counter[str]) -> Optional[float]:
    if score is None:
        return None
    if not domain_counts:
        return _clamp(score)

    config = _get_overrides().get("penalties", {})
    threshold = int(config.get("volume_threshold", 25))
    step = float(config.get("volume_penalty_step", 0.01))
    max_penalty = float(config.get("volume_max_penalty", 0.15))

    max_count = max(domain_counts.values())
    penalty = 0.0
    if max_count >= threshold:
        penalty = min((max_count - threshold + 1) * step, max_penalty)

    return _clamp(score - penalty)


def average_reliability(values: list[Optional[float]]) -> Optional[float]:
    valid = [value for value in values if isinstance(value, (int, float))]
    if not valid:
        return None
    return _clamp(sum(valid) / len(valid))
