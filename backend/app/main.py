

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from app import models, schemas, crud
from app.database import engine, get_db, SessionLocal

logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

async def _cleanup_loop():
    """Delete expired sql_meta rows once per hour."""
    while True:
        await asyncio.sleep(3600)
        db = SessionLocal()
        try:
            deleted = crud.delete_expired_sql_meta(db)
            if deleted:
                logger.info("Cleaned up %d expired sql_meta rows", deleted)
        except Exception as e:
            logger.error("sql_meta cleanup error: %s", e)
        finally:
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()

app = FastAPI(title="Chat App API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Chat App API"}

# Conversation endpoints
@app.post("/conversations/", response_model=schemas.Conversation)
def create_conversation(
    conversation: schemas.ConversationCreate,
    db: Session = Depends(get_db)
):
    return crud.create_conversation(db, conversation)

@app.get("/conversations/", response_model=List[schemas.ConversationSummary])
def list_conversations(
    user_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return crud.get_conversations(db, user_id=user_id, skip=skip, limit=limit)

@app.get("/conversations/{conversation_id}", response_model=schemas.Conversation)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    db_conversation = crud.get_conversation(db, conversation_id)
    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return db_conversation

@app.delete("/conversations/{conversation_id}/messages/{message_id}")
def delete_message(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db)
):
    success = crud.delete_message(db, conversation_id, message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message deleted successfully"}

@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    success = crud.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted successfully"}

# Message endpoints
@app.post("/conversations/{conversation_id}/messages/", response_model=schemas.Message)
def create_message(
    conversation_id: str,
    message: schemas.MessageCreate,
    db: Session = Depends(get_db)
):
    # Verify conversation exists
    db_conversation = crud.get_conversation(db, conversation_id)
    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return crud.create_message(db, conversation_id, message)

@app.get("/conversations/{conversation_id}/messages/", response_model=List[schemas.Message])
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    # Verify conversation exists
    db_conversation = crud.get_conversation(db, conversation_id)
    if db_conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return crud.get_messages(db, conversation_id)
