from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import os

from app import models, schemas

SQL_META_TTL_HOURS = int(os.getenv("SQL_META_TTL_HOURS", "48"))

# Conversation CRUD operations
def create_conversation(db: Session, conversation: schemas.ConversationCreate) -> models.Conversation:
    db_conversation = models.Conversation(
        title=conversation.title,
        user_id=conversation.user_id
    )
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    return db_conversation

def get_conversation(db: Session, conversation_id: str) -> Optional[models.Conversation]:
    return db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()

def get_conversations(db: Session, user_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[dict]:
    query = db.query(models.Conversation)
    if user_id:
        query = query.filter(models.Conversation.user_id == user_id)
    conversations = query.order_by(models.Conversation.updated_at.desc()).offset(skip).limit(limit).all()

    # Add message count and last message preview for each conversation
    result = []
    for conv in conversations:
        messages = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).order_by(models.Message.created_at.desc()).limit(1).all()

        message_count = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).count()

        last_message = messages[0].content if messages else None

        result.append({
            'id': conv.id,
            'title': conv.title,
            'created_at': conv.created_at,
            'updated_at': conv.updated_at,
            'user_id': conv.user_id,
            'message_count': message_count,
            'last_message': last_message
        })

    return result

def delete_conversation(db: Session, conversation_id: str) -> bool:
    db_conversation = get_conversation(db, conversation_id)
    if db_conversation:
        db.delete(db_conversation)
        db.commit()
        return True
    return False

def update_conversation_timestamp(db: Session, conversation_id: str):
    db_conversation = get_conversation(db, conversation_id)
    if db_conversation:
        db_conversation.updated_at = datetime.utcnow()
        db.commit()

# Message CRUD operations
def create_message(db: Session, conversation_id: str, message: schemas.MessageCreate) -> models.Message:
    db_message = models.Message(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content
    )
    db.add(db_message)
    db.flush()  # get the id before committing

    if message.sql_meta and (message.sql_meta.sql_query or message.sql_meta.blocked):
        db_sql_meta = models.MessageSqlMeta(
            message_id=db_message.id,
            sql_query=message.sql_meta.sql_query,
            row_count=message.sql_meta.row_count,
            duration_ms=message.sql_meta.duration_ms,
            blocked=message.sql_meta.blocked,
            expires_at=datetime.utcnow() + timedelta(hours=SQL_META_TTL_HOURS),
        )
        db.add(db_sql_meta)

    db.commit()
    db.refresh(db_message)

    # Update conversation timestamp
    update_conversation_timestamp(db, conversation_id)

    return db_message

def get_messages(db: Session, conversation_id: str) -> List[models.Message]:
    messages = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(models.Message.created_at.asc()).all()

    # Expire sql_meta in-memory so the response omits it without touching the row
    now = datetime.utcnow()
    for msg in messages:
        if msg.sql_meta and msg.sql_meta.expires_at < now:
            msg.sql_meta = None

    return messages

def delete_expired_sql_meta(db: Session) -> int:
    deleted = db.query(models.MessageSqlMeta).filter(
        models.MessageSqlMeta.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return deleted
