#!/bin/bash

# Script to validate Langfuse configuration consistency
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

echo -e "${BLUE}🔍 Validating Langfuse Configuration - Environment: $ENV${NC}"
echo -e "${BLUE}======================================================${NC}"

# Check if environment file exists
ENV_FILE="$PROJECT_ROOT/.env.$ENV"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file $ENV_FILE not found${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found environment file: $ENV_FILE${NC}"

# Load environment variables
set -a
source "$ENV_FILE"
set +a

# Validate required variables
echo -e "\n${YELLOW}🔧 Checking required Langfuse variables:${NC}"

required_vars=(
    "LANGFUSE_DB_PASSWORD"
    "LANGFUSE_NEXTAUTH_SECRET"
    "LANGFUSE_SALT"
    "LANGFUSE_HOST"
    "CLICKHOUSE_URL"
    "CLICKHOUSE_MIGRATION_URL"
    "CLICKHOUSE_USER"
)

missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ $var: Not set${NC}"
        missing_vars+=("$var")
    else
        # Mask sensitive values
        case $var in
            *PASSWORD*|*SECRET*|*SALT*)
                echo -e "${GREEN}✅ $var: ******** (set)${NC}"
                ;;
            *)
                echo -e "${GREEN}✅ $var: ${!var}${NC}"
                ;;
        esac
    fi
done

# Check optional but recommended variables
echo -e "\n${YELLOW}🔧 Checking optional Langfuse variables:${NC}"

optional_vars=(
    "LANGFUSE_PUBLIC_KEY"
    "LANGFUSE_SECRET_KEY"
    "LANGFUSE_DATABASE_URL"
    "LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES"
    "TELEMETRY_ENABLED"
    "CORS_ALLOWED_ORIGINS"
    "CLICKHOUSE_PASSWORD"
)

for var in "${optional_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${YELLOW}⚠️  $var: Not set (optional)${NC}"
    else
        case $var in
            *KEY*|*SECRET*)
                echo -e "${GREEN}✅ $var: ******** (set)${NC}"
                ;;
            *)
                echo -e "${GREEN}✅ $var: ${!var}${NC}"
                ;;
        esac
    fi
done

# Validate configuration consistency
echo -e "\n${YELLOW}🔍 Checking configuration consistency:${NC}"

# Check if LANGFUSE_HOST matches expected local development value
if [ "$ENV" = "local" ] && [ "$LANGFUSE_HOST" != "http://localhost:3001" ]; then
    echo -e "${YELLOW}⚠️  LANGFUSE_HOST is '$LANGFUSE_HOST' but expected 'http://localhost:3001' for local development${NC}"
fi

# Check if DATABASE_URL matches password
if [ -n "$LANGFUSE_DATABASE_URL" ]; then
    if [[ "$LANGFUSE_DATABASE_URL" == *"$LANGFUSE_DB_PASSWORD"* ]]; then
        echo -e "${GREEN}✅ Database URL password matches LANGFUSE_DB_PASSWORD${NC}"
    else
        echo -e "${RED}❌ Database URL password doesn't match LANGFUSE_DB_PASSWORD${NC}"
    fi
fi

# Final validation
echo -e "\n${BLUE}======================================================${NC}"
if [ ${#missing_vars[@]} -eq 0 ]; then
    echo -e "${GREEN}✅ Configuration validation passed!${NC}"

    if [ "$LANGFUSE_PUBLIC_KEY" = "your-langfuse-public-key" ]; then
        echo -e "\n${YELLOW}📝 Next steps:${NC}"
        echo -e "1. Start Langfuse: ./langfuse/langfuse.sh start $ENV"
        echo -e "2. Open http://localhost:3001 and create an account"
        echo -e "3. Generate API keys and update $ENV_FILE"
        echo -e "4. Run this validation again to confirm setup"
    else
        echo -e "\n${GREEN}🎉 Langfuse appears to be fully configured!${NC}"
    fi

    exit 0
else
    echo -e "${RED}❌ Configuration validation failed!${NC}"
    echo -e "${RED}Missing required variables: ${missing_vars[*]}${NC}"
    exit 1
fi