import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from database import Base


CHAT_MESSAGE_STATE = Enum(
    "pending",
    "streaming",
    "ready",
    "error",
    name="chat_message_state",
)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    org_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="새 대화")
    summary = Column(Text, nullable=True)
    context_type = Column(String(64), nullable=True, index=True)
    context_id = Column(String(128), nullable=True, index=True)
    message_count = Column(Integer, nullable=False, default=0)
    token_budget = Column(Integer, nullable=True)
    summary_tokens = Column(Integer, nullable=True)
    memory_snapshot = Column(JSONB, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True)
    version = Column(BigInteger, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_chat_messages_session_seq"),
        UniqueConstraint("idempotency_key", name="uq_chat_messages_idempotency_key"),
        {"extend_existing": True},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq = Column(Integer, nullable=False)
    turn_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    retry_of_message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id"), nullable=True, index=True)
    reply_to_message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id"), nullable=True, index=True)
    role = Column(String(32), nullable=False, index=True)
    state = Column(CHAT_MESSAGE_STATE, nullable=False, default="pending", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    meta = Column(JSONB, nullable=False, default=dict)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChatMessageArchive(Base):
    __tablename__ = "chat_messages_archive"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    payload = Column(JSONB, nullable=False)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChatAudit(Base):
    __tablename__ = "chat_audit"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    message_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
