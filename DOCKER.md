# Docker Setup Guide

This guide explains how to run the Chat App using Docker containers.

## Architecture

The application consists of three services:

1. **PostgreSQL** - Database for storing conversations and messages
2. **Backend** - FastAPI server (Python)
3. **Frontend** - React app served by Nginx

## Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)

## Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.docker .env
   ```

2. **Edit `.env` file and add your Gemini API key:**
   ```bash
   VITE_GEMINI_API_KEY=your_actual_api_key_here
   ```

3. **Start all services:**
   ```bash
   ./start.sh
   ```

4. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Commands

The `start.sh` script provides several commands:

```bash
./start.sh up        # Start all services (default)
./start.sh down      # Stop all services
./start.sh restart   # Restart all services
./start.sh logs      # View logs
./start.sh status    # Show service status
./start.sh clean     # Remove everything (containers, volumes, images)
```

## Manual Docker Compose Commands

If you prefer to use docker-compose directly:

```bash
# Start services
docker-compose up -d --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres

# Restart a specific service
docker-compose restart backend

# Rebuild and restart
docker-compose up -d --build --force-recreate
```

## Service Ports

| Service  | Port | Description |
|----------|------|-------------|
| Frontend | 3000 | React app UI |
| Backend  | 8000 | FastAPI server |
| PostgreSQL | 5432 | Database |

## Data Persistence

PostgreSQL data is persisted in a Docker volume named `postgres_data`. This means your conversations and messages will persist even if you restart the containers.

To remove all data:
```bash
./start.sh clean
```

## Troubleshooting

### Services won't start

Check if ports are already in use:
```bash
# Check what's using port 3000, 8000, or 5432
lsof -i :3000
lsof -i :8000
lsof -i :5432
```

### View service logs

```bash
./start.sh logs

# Or for specific service
docker-compose logs -f backend
```

### Rebuild from scratch

```bash
./start.sh clean
./start.sh up
```

### Access database directly

```bash
docker exec -it chat-app-db psql -U postgres -d chat_app
```

## Development

### Hot reload during development

For development with hot reload, you may want to run services individually:

**Backend with hot reload:**
```bash
docker-compose up postgres -d
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

**Frontend with hot reload:**
```bash
cd chat-app
npm run dev
```

### Update dependencies

**Backend:**
```bash
cd backend
# Update requirements.txt
docker-compose build backend
docker-compose up -d backend
```

**Frontend:**
```bash
cd chat-app
# Update package.json
docker-compose build frontend
docker-compose up -d frontend
```

## Production Considerations

For production deployment, consider:

1. **Environment Variables**: Use secrets management instead of .env files
2. **HTTPS**: Add SSL certificates and reverse proxy (nginx/traefik)
3. **Database**: Use managed PostgreSQL service or separate DB server
4. **Scaling**: Use container orchestration (Kubernetes, Docker Swarm)
5. **Monitoring**: Add logging, metrics, and health checks
6. **Backup**: Implement database backup strategy

## Network

All services run in the same Docker network and can communicate with each other using service names:
- Backend can reach database at `postgres:5432`
- Frontend makes API calls to backend at configured URL

## Stopping the Application

```bash
# Stop services (keeps data)
./start.sh stop

# Stop services and remove volumes (deletes data)
./start.sh clean
```
