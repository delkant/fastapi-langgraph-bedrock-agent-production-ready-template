#!/bin/bash

# Script to stop Langfuse services
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENV=${1:-local}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🛑 Stopping Langfuse services for environment: $ENV${NC}"

# Check if environment file exists
ENV_FILE="$PROJECT_ROOT/.env.$ENV"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file $ENV_FILE not found${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Using environment file: $ENV_FILE${NC}"

# Navigate to project root
cd "$PROJECT_ROOT"

# Stop services
echo -e "${YELLOW}🐳 Stopping Langfuse services...${NC}"
APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" stop langfuse langfuse-db

# Check if services are stopped
if ! docker-compose ps langfuse | grep -q "Up"; then
    echo -e "${GREEN}✅ Langfuse server stopped${NC}"
else
    echo -e "${YELLOW}⚠️  Langfuse server may still be stopping...${NC}"
fi

if ! docker-compose ps langfuse-db | grep -q "Up"; then
    echo -e "${GREEN}✅ Langfuse database stopped${NC}"
else
    echo -e "${YELLOW}⚠️  Langfuse database may still be stopping...${NC}"
fi

echo -e "${BLUE}🎉 Langfuse services stopped successfully!${NC}"

# Optional: Ask if user wants to remove containers
read -p "Do you want to remove the stopped containers? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🗑️  Removing containers...${NC}"
    APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" rm -f langfuse langfuse-db
    echo -e "${GREEN}✅ Containers removed${NC}"
fi