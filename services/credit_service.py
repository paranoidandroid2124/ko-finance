import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


def charge_credits(db: Session, *, user_id: Optional[uuid.UUID], cost: int = 1) -> None:
    """
    Deduct credits from profiles table. Raises HTTPException if insufficient.
    """
    if user_id is None:
        # 비로그인 사용자는 크레딧 차감하지 않음
        return
    result = db.execute(text("select credits from profiles where id = :uid for update"), {"uid": str(user_id)})
    row = result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "profile_not_found", "message": "프로필 정보를 찾을 수 없습니다."},
        )
    credits = row[0] or 0
    if credits < cost:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "credits_insufficient", "message": "남은 크레딧이 없습니다."},
        )
    db.execute(
        text("update profiles set credits = credits - :cost where id = :uid"),
        {"cost": cost, "uid": str(user_id)},
    )
