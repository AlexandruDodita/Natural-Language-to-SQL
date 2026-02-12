from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class MessageBase(BaseModel):
    role: str
    content: str

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: str
    conversation_id: str
    created_at: datetime

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

    class Config:
        from_attributes = True
