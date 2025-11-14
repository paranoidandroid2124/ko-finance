"""Helpers for onboarding state and sample content."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.logging import get_logger
from services.file_store import write_json_atomic

logger = get_logger(__name__)

_ONBOARDING_CONTENT_PATH = Path("uploads") / "admin" / "onboarding_samples.json"
_ONBOARDING_CONTENT_CACHE: Optional[Dict[str, Any]] = None

_DEFAULT_ONBOARDING_CONTENT: Dict[str, Any] = {
    "hero": {
        "title": "어서 오세요! 첫 3분 리서치 루틴을 안내해 드릴게요",
        "subtitle": "워치리스트·챗봇·리포트까지, 샘플 보드를 통해 하루 업무 플로우를 체험할 수 있습니다.",
        "highlights": [
            "공시/뉴스 모니터링 핵심만 추려서 보여드려요",
            "AI 애널리스트 답변과 근거 Diff 를 함께 확인할 수 있어요",
            "샘플 워크보드를 복사해서 바로 팀 공유 가능합니다",
        ],
    },
    "checklist": [
        {
            "id": "watchlist-rule",
            "title": "워치리스트 규칙 확인",
            "description": "자동으로 감지된 공시/뉴스 룰과 Slack 연동 예시를 살펴보세요.",
            "tips": ["샘플 룰을 복사해 나만의 룰을 만들 수 있어요."],
            "cta": {"label": "워치리스트 둘러보기", "href": "/alerts/watchlist"},
        },
        {
            "id": "chat-rag",
            "title": "AI 애널리스트에게 질문",
            "description": "Evidence-first 답변과 Diff 뷰어를 체험해 보세요.",
            "tips": ["질문 템플릿을 사용하면 더욱 빠르게 분석 시작!"],
            "cta": {"label": "샘플 질문 실행", "href": "/chat?sample=onboarding"},
        },
        {
            "id": "report-digest",
            "title": "일간 리포트/다이제스트",
            "description": "뉴스/이벤트 다이제스트가 어떻게 구성되는지 미리 확인하세요.",
            "tips": ["Slack/Email 채널 링크를 통해 팀 공유도 가능합니다."],
            "cta": {"label": "샘플 리포트 보기", "href": "/reports/digest?sample=onboarding"},
        },
    ],
    "sampleBoard": {
        "title": "샘플 리서치 허브",
        "sections": [
            {
                "id": "alerts",
                "title": "금일 감지된 공시/뉴스",
                "items": [
                    {
                        "type": "alert",
                        "badge": "공시",
                        "headline": "삼성전자, 1.5조 규모 파운드리 투자",
                        "summary": "시설투자 확대와 더불어 파운드리 라인 전환 계획을 공시했습니다.",
                        "link": "/alerts/watchlist?sample=1",
                        "meta": {"ticker": "005930.KS", "publishedAt": "오늘 09:10"},
                    },
                    {
                        "type": "news",
                        "badge": "뉴스",
                        "headline": "배터리 3사, IRA 세액공제 확대 수혜",
                        "summary": "미 에너지부 가이드라인 변경으로 국내 셀 업체들의 수혜 폭이 커질 전망입니다.",
                        "link": "/alerts/watchlist?sample=2",
                        "meta": {"ticker": "373220.KS", "publishedAt": "오늘 08:45"},
                    },
                ],
            },
            {
                "id": "chat",
                "title": "AI 애널리스트 Q&A",
                "items": [
                    {
                        "type": "chat",
                        "question": "2분기 삼성전자 실적과 전년 동기 대비 관전 포인트는?",
                        "answerPreview": "메모리 ASP 하락으로 YoY 감소했으나, HBM 수요확대로 하반기 턴어라운드 기대...",
                        "link": "/chat?sample=earnings",
                    }
                ],
            },
            {
                "id": "digest",
                "title": "뉴스 다이제스트",
                "items": [
                    {
                        "type": "digest",
                        "headline": "전력·에너지 정책 업데이트",
                        "bullets": [
                            "산업부, 신재생 발전 비중 2030년 32% 목표",
                            "에너지 공기업, 2분기부터 REC 의무비율 상향 예정",
                        ],
                        "link": "/reports/digest?sample=power",
                    }
                ],
            },
        ],
    },
}


def load_onboarding_content(*, reload: bool = False) -> Dict[str, Any]:
    global _ONBOARDING_CONTENT_CACHE
    if _ONBOARDING_CONTENT_CACHE is not None and not reload:
        return deepcopy(_ONBOARDING_CONTENT_CACHE)

    path = _ONBOARDING_CONTENT_PATH
    if not path.exists():
        write_json_atomic(path, _DEFAULT_ONBOARDING_CONTENT, logger=logger)
        payload = deepcopy(_DEFAULT_ONBOARDING_CONTENT)
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load onboarding samples from %s: %s", path, exc)
            payload = deepcopy(_DEFAULT_ONBOARDING_CONTENT)

    _ONBOARDING_CONTENT_CACHE = deepcopy(payload)
    return deepcopy(payload)


def ensure_first_login_metadata(session: Session, *, user_id: str) -> bool:
    row = (
        session.execute(
            text(
                """
                SELECT first_login_at, onboarded_at
                FROM "users"
                WHERE id = :user_id
                FOR UPDATE
                """
            ),
            {"user_id": user_id},
        )
        .mappings()
        .first()
    )
    if not row:
        return False

    if row["first_login_at"] is None:
        session.execute(
            text("UPDATE \"users\" SET first_login_at = :now WHERE id = :user_id"),
            {"now": datetime.now(timezone.utc), "user_id": user_id},
        )
    return row.get("onboarded_at") is None


def mark_onboarding_completed(
    session: Session,
    *,
    user_id: str,
    completed_steps: Optional[Sequence[str]],
) -> None:
    checklist_json = json.dumps({"steps": list(dict.fromkeys(completed_steps or []))}, ensure_ascii=False)
    session.execute(
        text(
            """
            UPDATE "users"
            SET onboarded_at = COALESCE(onboarded_at, NOW()),
                onboarding_checklist = CAST(:checklist AS JSONB)
            WHERE id = :user_id
            """
        ),
        {"checklist": checklist_json, "user_id": user_id},
    )


def user_needs_onboarding(session: Session, *, user_id: str) -> bool:
    row = session.execute(
        text("SELECT onboarded_at FROM \"users\" WHERE id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    if not row:
        return False
    return row.get("onboarded_at") is None


__all__ = [
    "ensure_first_login_metadata",
    "load_onboarding_content",
    "mark_onboarding_completed",
    "user_needs_onboarding",
]
