#!/bin/bash

# Script to check Langfuse services status
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

echo -e "${BLUE}📊 Langfuse Services Status - Environment: $ENV${NC}"
echo -e "${BLUE}================================================${NC}"

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose not found${NC}"
    exit 1
fi

# Function to check service status
check_service_status() {
    local service_name=$1
    local display_name=$2

    if docker-compose ps "$service_name" | grep -q "Up"; then
        local status=$(docker-compose ps "$service_name" | grep "$service_name" | awk '{print $4}')
        echo -e "${GREEN}✅ $display_name: Running ($status)${NC}"
        return 0
    else
        echo -e "${RED}❌ $display_name: Not running${NC}"
        return 1
    fi
}

# Function to check port connectivity
check_port() {
    local port=$1
    local service_name=$2

    if nc -z localhost "$port" 2>/dev/null; then
        echo -e "${GREEN}✅ Port $port ($service_name): Accessible${NC}"
        return 0
    else
        echo -e "${RED}❌ Port $port ($service_name): Not accessible${NC}"
        return 1
    fi
}

# Function to check HTTP endpoint
check_http() {
    local url=$1
    local service_name=$2

    if curl -f -s "$url" > /dev/null; then
        local response=$(curl -s "$url")
        echo -e "${GREEN}✅ $service_name HTTP: Responding${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name HTTP: Not responding${NC}"
        return 1
    fi
}

echo -e "\n${YELLOW}🐳 Docker Services:${NC}"
# Check service containers
langfuse_db_running=false
langfuse_server_running=false

if check_service_status "langfuse-db" "Langfuse Database"; then
    langfuse_db_running=true
fi

if check_service_status "langfuse" "Langfuse Server"; then
    langfuse_server_running=true
fi

echo -e "\n${YELLOW}🌐 Port Connectivity:${NC}"
# Check port accessibility
check_port 5433 "Langfuse Database"
check_port 3001 "Langfuse Web UI"

echo -e "\n${YELLOW}🔌 HTTP Endpoints:${NC}"
# Check HTTP endpoints
if $langfuse_server_running; then
    check_http "http://localhost:3001/api/public/health" "Langfuse API"
    check_http "http://localhost:3001" "Langfuse Web UI"
fi

echo -e "\n${YELLOW}💾 Database Status:${NC}"
if $langfuse_db_running; then
    # Try to connect to database
    if docker exec -i langfuse-postgres psql -U langfuse -d langfuse -c "SELECT version();" &>/dev/null; then
        echo -e "${GREEN}✅ Database connection: Working${NC}"

        # Get some basic stats
        table_count=$(docker exec -i langfuse-postgres psql -U langfuse -d langfuse -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        if [[ "$table_count" =~ ^[0-9]+$ ]] && [ "$table_count" -gt 0 ]; then
            echo -e "${GREEN}✅ Database tables: $table_count tables initialized${NC}"
        else
            echo -e "${YELLOW}⚠️  Database tables: Not yet initialized${NC}"
        fi
    else
        echo -e "${RED}❌ Database connection: Failed${NC}"
    fi
fi

echo -e "\n${YELLOW}📝 Quick Actions:${NC}"
if $langfuse_server_running && $langfuse_db_running; then
    echo -e "${GREEN}🌐 Access Langfuse: http://localhost:3001${NC}"
    echo -e "${GREEN}🔧 View logs: docker-compose logs -f langfuse${NC}"
    echo -e "${GREEN}🗄️  Database logs: docker-compose logs -f langfuse-db${NC}"
else
    echo -e "${YELLOW}🚀 Start services: ./langfuse/scripts/start-langfuse.sh $ENV${NC}"
fi

echo -e "${YELLOW}🛑 Stop services: ./langfuse/scripts/stop-langfuse.sh $ENV${NC}"
echo -e "${YELLOW}🔄 Reset data: ./langfuse/scripts/reset-langfuse.sh $ENV${NC}"

echo -e "\n${BLUE}================================================${NC}"

# Overall status
if $langfuse_server_running && $langfuse_db_running; then
    echo -e "${GREEN}✅ Overall Status: All Langfuse services are running${NC}"
    exit 0
else
    echo -e "${RED}❌ Overall Status: Some Langfuse services are not running${NC}"
    exit 1
fi