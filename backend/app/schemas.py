from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

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

class MessageBase(BaseModel):
    role: str
    content: str

class MessageCreate(MessageBase):
    sql_meta: Optional[SqlMetaCreate] = None

class Message(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime
    sql_meta: Optional[SqlMetaResponse] = None

    class Config:
        from_attributes = True

class ConversationBase(BaseModel):
    title: str

class ConversationCreate(ConversationBase):
    user_id: Optional[str] = None

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
