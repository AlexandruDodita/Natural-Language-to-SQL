#!/bin/bash

# Chat App Startup Script
# This script starts all services using Docker Compose

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}  Chat App - Starting Services${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Creating .env file from .env.docker template..."
    cp .env.docker .env
    echo -e "${YELLOW}Please edit .env file and add your VITE_GEMINI_API_KEY${NC}"
    echo -e "${YELLOW}Then run this script again.${NC}"
    exit 1
fi

# Check if VITE_GEMINI_API_KEY is set
if grep -q "your_gemini_api_key_here" .env; then
    echo -e "${RED}Error: Please set your VITE_GEMINI_API_KEY in .env file${NC}"
    exit 1
fi

# Parse command line arguments
COMMAND=${1:-up}

case $COMMAND in
    up|start)
        echo -e "${GREEN}Starting all services...${NC}"
        docker-compose up -d --build
        echo ""
        echo -e "${GREEN}Services started successfully!${NC}"
        echo ""
        echo -e "Frontend: ${GREEN}http://localhost:3000${NC}"
        echo -e "Backend API: ${GREEN}http://localhost:8000${NC}"
        echo -e "API Docs: ${GREEN}http://localhost:8000/docs${NC}"
        echo ""
        echo -e "To view logs: ${YELLOW}docker-compose logs -f${NC}"
        echo -e "To stop: ${YELLOW}./start.sh stop${NC}"
        ;;

    down|stop)
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker-compose down
        echo -e "${GREEN}Services stopped${NC}"
        ;;

    restart)
        echo -e "${YELLOW}Restarting all services...${NC}"
        docker-compose down
        docker-compose up -d --build
        echo -e "${GREEN}Services restarted${NC}"
        ;;

    logs)
        docker-compose logs -f
        ;;

    clean)
        echo -e "${RED}Stopping and removing all containers, volumes, and images...${NC}"
        docker-compose down -v --rmi all
        echo -e "${GREEN}Cleanup complete${NC}"
        ;;

    status)
        docker-compose ps
        ;;

    *)
        echo "Usage: ./start.sh [command]"
        echo ""
        echo "Commands:"
        echo "  up, start    - Start all services (default)"
        echo "  down, stop   - Stop all services"
        echo "  restart      - Restart all services"
        echo "  logs         - Show logs"
        echo "  status       - Show service status"
        echo "  clean        - Remove all containers, volumes, and images"
        exit 1
        ;;
esac
