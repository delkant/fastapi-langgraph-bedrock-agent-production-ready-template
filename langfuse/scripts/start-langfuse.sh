#!/bin/bash

# Script to start Langfuse services
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

echo -e "${BLUE}🚀 Starting Langfuse services for environment: $ENV${NC}"

# Check if environment file exists
ENV_FILE="$PROJECT_ROOT/.env.$ENV"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file $ENV_FILE not found${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Using environment file: $ENV_FILE${NC}"

# Navigate to project root
cd "$PROJECT_ROOT"

# Start services using docker-compose
echo -e "${YELLOW}🐳 Starting Langfuse services...${NC}"
APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" up -d langfuse-db langfuse

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check if services are running
if docker-compose ps langfuse-db | grep -q "Up"; then
    echo -e "${GREEN}✅ Langfuse database is running${NC}"
else
    echo -e "${RED}❌ Langfuse database failed to start${NC}"
    docker-compose logs langfuse-db
    exit 1
fi

if docker-compose ps langfuse | grep -q "Up"; then
    echo -e "${GREEN}✅ Langfuse server is running${NC}"
else
    echo -e "${RED}❌ Langfuse server failed to start${NC}"
    docker-compose logs langfuse
    exit 1
fi

# Test connectivity
echo -e "${YELLOW}🔍 Testing Langfuse connectivity...${NC}"
sleep 10  # Give more time for Langfuse to fully start

if curl -f -s http://localhost:3001/api/public/health > /dev/null; then
    echo -e "${GREEN}✅ Langfuse is responding at http://localhost:3001${NC}"
else
    echo -e "${YELLOW}⚠️  Langfuse may still be starting up. Check manually at http://localhost:3001${NC}"
fi

echo -e "${BLUE}🎉 Langfuse services started successfully!${NC}"
echo -e "${GREEN}📊 Access Langfuse at: http://localhost:3001${NC}"
echo -e "${GREEN}🗄️  Database is running on: localhost:5344${NC}"

echo -e "\n${YELLOW}📝 Next steps:${NC}"
echo -e "1. Open http://localhost:3001 in your browser"
echo -e "2. Create an admin account"
echo -e "3. Generate API keys"
echo -e "4. Update your .env.$ENV file with the generated keys"