from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional

class SqlMetaCreate(BaseModel):
    sql_query: Optional[str] = None
    row_count: Optional[int] = None
    duration_ms: Optional[float] = None
    blocked: Optional[str] = None

class SqlMetaResponse(BaseModel):
    sql_query: Optional[str] = None
    row_count: Optional[int] = None
    duration_ms: Optional[float] = None
    blocked: Optional[str] = None

    class Config:
        from_attributes = True

class ArtifactCreate(BaseModel):
    """Result set plus the full pipeline metadata, so a reloaded conversation
    still has its table, its chart and its provenance."""

    payload: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

class ArtifactResponse(BaseModel):
    payload: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    role: str
    content: str

class MessageCreate(MessageBase):
    sql_meta: Optional[SqlMetaCreate] = None
    artifact: Optional[ArtifactCreate] = None

class Message(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime
    sql_meta: Optional[SqlMetaResponse] = None
    artifact: Optional[ArtifactResponse] = None

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    title: str

class ConversationCreate(ConversationBase):
    user_id: Optional[str] = None

class ConversationUpdate(BaseModel):
    title: str

class Conversation(ConversationBase):
    id: str
    created_at: datetime
    updated_at: datetime
    user_id: Optional[str] = None
    messages: List[Message] = []

    class Config:
        from_attributes = True

class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    user_id: Optional[str] = None
    message_count: int = 0
    last_message: Optional[str] = None

    class Config:
        from_attributes = True
