#!/bin/bash

# Script to reset Langfuse data (⚠️ DANGEROUS - DELETES ALL DATA)
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

echo -e "${RED}⚠️  WARNING: This will DELETE ALL Langfuse data!${NC}"
echo -e "${YELLOW}Environment: $ENV${NC}"
echo -e "${YELLOW}This includes:${NC}"
echo -e "  - All traces and spans"
echo -e "  - All projects and API keys"
echo -e "  - All user accounts"
echo -e "  - All configurations"

echo -e "\n${RED}This action cannot be undone!${NC}\n"

# Confirmation prompts
read -p "Are you sure you want to reset ALL Langfuse data? Type 'yes' to continue: " -r
if [ "$REPLY" != "yes" ]; then
    echo -e "${GREEN}✅ Reset cancelled${NC}"
    exit 0
fi

read -p "Last chance! This will permanently delete everything. Type 'DELETE EVERYTHING' to proceed: " -r
if [ "$REPLY" != "DELETE EVERYTHING" ]; then
    echo -e "${GREEN}✅ Reset cancelled${NC}"
    exit 0
fi

echo -e "${BLUE}🗑️  Resetting Langfuse data...${NC}"

# Check if environment file exists
ENV_FILE="$PROJECT_ROOT/.env.$ENV"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file $ENV_FILE not found${NC}"
    exit 1
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Stop services first
echo -e "${YELLOW}🛑 Stopping Langfuse services...${NC}"
APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" stop langfuse langfuse-db || true

# Remove containers and volumes
echo -e "${YELLOW}🗑️  Removing containers and data volumes...${NC}"
APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" down langfuse langfuse-db
docker volume rm "$(basename $PWD)_langfuse-postgres-data" 2>/dev/null || true

# Restart services
echo -e "${YELLOW}🚀 Starting fresh Langfuse services...${NC}"
APP_ENV=$ENV docker-compose --env-file "$ENV_FILE" up -d langfuse-db langfuse

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to initialize...${NC}"
sleep 15

# Test connectivity
if curl -f -s http://localhost:3001/api/public/health > /dev/null; then
    echo -e "${GREEN}✅ Fresh Langfuse instance is ready at http://localhost:3001${NC}"
else
    echo -e "${YELLOW}⚠️  Langfuse may still be starting up. Check manually at http://localhost:3001${NC}"
fi

echo -e "${BLUE}🎉 Langfuse has been reset successfully!${NC}"
echo -e "\n${YELLOW}📝 Next steps:${NC}"
echo -e "1. Open http://localhost:3001 in your browser"
echo -e "2. Create a new admin account"
echo -e "3. Generate new API keys"
echo -e "4. Update your .env.$ENV file with the new keys"

echo -e "\n${RED}⚠️  Don't forget to update your API keys in the environment file!${NC}"