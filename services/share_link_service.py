"""Service layer for share link operations."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.share_link import ShareLink


def _generate_token(length: int = 12) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)[:length]


def create_share_link(
    db: Session,
    resource_type: str,
    resource_id: UUID,
    user_id: UUID,
    title: Optional[str] = None,
    expires_in_days: Optional[int] = None,
) -> ShareLink:
    """Create a new share link for a resource.
    
    Args:
        db: Database session
        resource_type: Type of resource ('chat_session' or 'report')
        resource_id: ID of the resource being shared
        user_id: ID of the user creating the share link
        title: Optional custom title for the share
        expires_in_days: Number of days until link expires (None = never expires)
    
    Returns:
        ShareLink: The created share link
    """
    if resource_type not in ("chat_session", "report"):
        raise ValueError(f"Invalid resource_type: {resource_type}")
    
    # Generate unique token
    token = _generate_token()
    while db.query(ShareLink).filter(ShareLink.token == token).first():
        token = _generate_token()
    
    # Calculate expiration
    expires_at = None
    if expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    
    share_link = ShareLink(
        token=token,
        resource_type=resource_type,
        resource_id=resource_id,
        created_by=user_id,
        title=title,
        expires_at=expires_at,
    )
    
    db.add(share_link)
    db.commit()
    db.refresh(share_link)
    
    return share_link


def get_share_link(db: Session, token: str) -> Optional[ShareLink]:
    """Retrieve a share link by token.
    
    Args:
        db: Database session
        token: The share link token
    
    Returns:
        ShareLink if found and not expired, None otherwise
    """
    share_link = db.query(ShareLink).filter(ShareLink.token == token).first()
    
    if not share_link:
        return None
    
    # Check if expired
    if share_link.expires_at and share_link.expires_at < datetime.now(timezone.utc):
        return None
    
    return share_link


def increment_view_count(db: Session, token: str) -> None:
    """Increment the view count for a share link.
    
    Args:
        db: Database session
        token: The share link token
    """
    share_link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if share_link:
        share_link.view_count += 1
        db.commit()


def delete_share_link(db: Session, token: str, user_id: UUID) -> bool:
    """Delete a share link (only if created by the user).
    
    Args:
        db: Database session
        token: The share link token
        user_id: ID of the user requesting deletion
    
    Returns:
        True if deleted, False if not found or unauthorized
    """
    share_link = db.query(ShareLink).filter(
        ShareLink.token == token,
        ShareLink.created_by == user_id
    ).first()
    
    if not share_link:
        return False
    
    db.delete(share_link)
    db.commit()
    return True


def get_share_links_by_resource(
    db: Session,
    resource_type: str,
    resource_id: UUID,
    user_id: UUID
) -> list[ShareLink]:
    """Get all share links for a specific resource created by a user.
    
    Args:
        db: Database session
        resource_type: Type of resource
        resource_id: ID of the resource
        user_id: ID of the user
    
    Returns:
        List of ShareLink objects
    """
    return db.query(ShareLink).filter(
        ShareLink.resource_type == resource_type,
        ShareLink.resource_id == resource_id,
        ShareLink.created_by == user_id
    ).all()
