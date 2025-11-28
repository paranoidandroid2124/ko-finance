"""API endpoints for share link functionality."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.chat import ChatMessage, ChatSession
from models.share_link import ShareLink
from services import share_link_service
from services.plan_service import PlanContext
from services.web_utils import parse_uuid
from web.deps import require_plan_feature

router = APIRouter(tags=["Share"])


# Request/Response schemas
class CreateShareLinkRequest(BaseModel):
    resource_type: str = Field(..., description="Type of resource: 'chat_session' or 'report'")
    resource_id: UUID = Field(..., description="ID of the resource to share")
    title: Optional[str] = Field(None, description="Optional custom title")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")


class CreateShareLinkResponse(BaseModel):
    token: str
    url: str
    expires_at: Optional[str] = None


class ShareLinkInfoResponse(BaseModel):
    resource_type: str
    title: Optional[str]
    created_at: str
    view_count: int
    data: dict


# Authenticated endpoints
@router.post(
    "/share/create",
    response_model=CreateShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공유 링크 생성"
)
def create_share_link(
    payload: CreateShareLinkRequest,
    x_user_id: Optional[str] = Depends(lambda: None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
):
    """Create a shareable link for a chat session or report."""
    from fastapi import Header, Request
    from starlette.requests import Request as StarletteRequest
    
    # Get user_id from request state
    # Note: This assumes auth_context_middleware has populated request.state.user
    # For now, we'll use x_user_id header as fallback
    user_id = parse_uuid(x_user_id)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Verify resource exists and user has access
    if payload.resource_type == "chat_session":
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.resource_id,
            ChatSession.user_id == user_id
        ).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied"
            )
    elif payload.resource_type == "report":
        # TODO: Add Report model verification once available
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource_type"
        )
    
    # Create share link
    share_link = share_link_service.create_share_link(
        db=db,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        user_id=user_id,
        title=payload.title,
        expires_in_days=payload.expires_in_days
    )
    
    # Build URL (use environment variable for base URL in production)
    base_url = "http://localhost:3000"  # TODO: Use proper config
    share_url = f"{base_url}/share/{share_link.token}"
    
    return CreateShareLinkResponse(
        token=share_link.token,
        url=share_url,
        expires_at=share_link.expires_at.isoformat() if share_link.expires_at else None
    )


@router.delete(
    "/share/{token}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="공유 링크 삭제"
)
def delete_share_link(
    token: str,
    x_user_id: Optional[str] = Depends(lambda: None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("rag.core")),
):
    """Delete a share link (revoke access)."""
    user_id = parse_uuid(x_user_id)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    deleted = share_link_service.delete_share_link(db, token, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or access denied"
        )
    
    return None


# Public endpoint (no authentication required)
@router.get(
    "/public/share/{token}",
    response_model=ShareLinkInfoResponse,
    summary="공유된 컨텐츠 조회"
)
def get_shared_content(
    token: str,
    db: Session = Depends(get_db),
):
    """Get shared content by token (public access)."""
    share_link = share_link_service.get_share_link(db, token)
    
    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found or expired"
        )
    
    # Increment view count
    share_link_service.increment_view_count(db, token)
    
    # Fetch resource data
    data = {}
    if share_link.resource_type == "chat_session":
        session = db.query(ChatSession).filter(ChatSession.id == share_link.resource_id).first()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found"
            )
        
        # Get messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.seq).all()
        
        data = {
            "session_id": str(session.id),
            "title": session.title or share_link.title,
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "meta": msg.meta,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
    elif share_link.resource_type == "report":
        # TODO: Implement report data fetching
        data = {"message": "Report sharing not yet implemented"}
    
    return ShareLinkInfoResponse(
        resource_type=share_link.resource_type,
        title=share_link.title,
        created_at=share_link.created_at.isoformat(),
        view_count=share_link.view_count,
        data=data
    )


__all__ = ["router"]
