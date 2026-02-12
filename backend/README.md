# Chat App Backend

FastAPI backend service for the chat application with PostgreSQL database.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up PostgreSQL database:
```bash
# Create database
createdb chat_app

# Or using psql
psql -U postgres
CREATE DATABASE chat_app;
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your database connection string
```

4. Run the server:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## Database Schema

### Conversations Table
- `id`: UUID primary key
- `title`: String
- `created_at`: DateTime
- `updated_at`: DateTime
- `user_id`: String (optional, for future auth)

### Messages Table
- `id`: UUID primary key
- `conversation_id`: Foreign key to conversations
- `role`: Enum (user, assistant)
- `content`: Text
- `created_at`: DateTime

## API Endpoints

### Conversations
- `POST /conversations/` - Create a new conversation
- `GET /conversations/` - List all conversations
- `GET /conversations/{id}` - Get a specific conversation with messages
- `DELETE /conversations/{id}` - Delete a conversation

### Messages
- `POST /conversations/{id}/messages/` - Add a message to a conversation
- `GET /conversations/{id}/messages/` - Get all messages for a conversation
