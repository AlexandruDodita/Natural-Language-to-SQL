from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum, Integer, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.database import Base

class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    user_id = Column(String, nullable=True)  # Optional for future user auth

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    sql_meta = relationship("MessageSqlMeta", back_populates="message", uselist=False, cascade="all, delete-orphan")
    artifact = relationship("MessageArtifact", back_populates="message", uselist=False, cascade="all, delete-orphan")

class MessageSqlMeta(Base):
    __tablename__ = "message_sql_meta"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    sql_query = Column(Text, nullable=True)
    row_count = Column(Integer, nullable=True)
    duration_ms = Column(Float, nullable=True)
    blocked = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="sql_meta")


class MessageArtifact(Base):
    """The result set and the full pipeline metadata of one answer.

    Kept in its own table (rather than as extra columns on ``message_sql_meta``)
    so an existing database picks it up from ``create_all`` without a migration.
    Same TTL as the SQL metadata: results are cached, not archived.
    """

    __tablename__ = "message_artifacts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    payload = Column(JSON, nullable=True)   # {columns, rows, chart, truncated}
    meta = Column(JSON, nullable=True)      # the whole sql_meta dict from the pipeline
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    message = relationship("Message", back_populates="artifact")
