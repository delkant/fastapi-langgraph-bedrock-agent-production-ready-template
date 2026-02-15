#!/bin/bash

# Health check script for Langfuse server
# This script checks if Langfuse is responding to HTTP requests

set -e

# Configuration
HOST=${LANGFUSE_HOST:-localhost}
PORT=${LANGFUSE_PORT:-3000}
TIMEOUT=${LANGFUSE_HEALTHCHECK_TIMEOUT:-10}

# Health check endpoint
HEALTH_URL="http://${HOST}:${PORT}/api/public/health"

# Function to check health
check_health() {
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$HEALTH_URL" || echo "000")

    if [ "$response_code" = "200" ]; then
        echo "✅ Langfuse is healthy (HTTP $response_code)"
        return 0
    else
        echo "❌ Langfuse health check failed (HTTP $response_code)"
        return 1
    fi
}

# Run health check
if check_health; then
    exit 0
else
    echo "🔍 Attempting to get more details..."
    curl -v --max-time $TIMEOUT "$HEALTH_URL" || true
    exit 1
fi