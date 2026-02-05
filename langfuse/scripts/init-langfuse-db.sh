#!/bin/bash

# Script to initialize Langfuse database
# This script creates the necessary database and user for Langfuse if they don't exist

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Database configuration
DB_HOST=${LANGFUSE_DB_HOST:-localhost}
DB_PORT=${LANGFUSE_DB_PORT:-5344}
DB_NAME=${LANGFUSE_DB_NAME:-langfuse}
DB_USER=${LANGFUSE_DB_USER:-langfuse}
DB_PASSWORD=${LANGFUSE_DB_PASSWORD:-langfuse_password}
POSTGRES_ADMIN_USER=${POSTGRES_USER:-postgres}
POSTGRES_ADMIN_PASSWORD=${POSTGRES_PASSWORD:-postgres}

echo -e "${GREEN}Initializing Langfuse database...${NC}"

# Wait for PostgreSQL to be ready
echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
until pg_isready -h $DB_HOST -p $DB_PORT -U $POSTGRES_ADMIN_USER; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo -e "${GREEN}PostgreSQL is ready!${NC}"

# Create database if it doesn't exist
echo -e "${YELLOW}Creating database '$DB_NAME' if it doesn't exist...${NC}"
PGPASSWORD=$POSTGRES_ADMIN_PASSWORD createdb -h $DB_HOST -p $DB_PORT -U $POSTGRES_ADMIN_USER $DB_NAME || true

# Create user if it doesn't exist
echo -e "${YELLOW}Creating user '$DB_USER' if it doesn't exist...${NC}"
PGPASSWORD=$POSTGRES_ADMIN_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $POSTGRES_ADMIN_USER -d $DB_NAME -c "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;
" || true

# Grant privileges
echo -e "${YELLOW}Granting privileges to user '$DB_USER'...${NC}"
PGPASSWORD=$POSTGRES_ADMIN_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $POSTGRES_ADMIN_USER -d $DB_NAME -c "
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DATABASE $DB_NAME OWNER TO $DB_USER;
" || true

echo -e "${GREEN}Langfuse database initialization completed!${NC}"
echo -e "${GREEN}Database: $DB_NAME${NC}"
echo -e "${GREEN}User: $DB_USER${NC}"
echo -e "${GREEN}Host: $DB_HOST:$DB_PORT${NC}"