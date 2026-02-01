#!/bin/bash

# Langfuse Management Script
# This script provides a unified interface for managing Langfuse services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ENV="local"

# Help function
show_help() {
    echo -e "${BLUE}Langfuse Management Script${NC}"
    echo -e "${BLUE}=========================${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC}"
    echo "  $0 <command> [environment]"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo -e "  ${GREEN}start${NC}     - Start Langfuse services"
    echo -e "  ${GREEN}stop${NC}      - Stop Langfuse services"
    echo -e "  ${GREEN}status${NC}    - Check Langfuse services status"
    echo -e "  ${GREEN}restart${NC}   - Restart Langfuse services"
    echo -e "  ${GREEN}logs${NC}      - View Langfuse logs"
    echo -e "  ${GREEN}reset${NC}     - Reset Langfuse data (⚠️ DANGEROUS)"
    echo -e "  ${GREEN}init${NC}      - Initialize Langfuse database"
    echo -e "  ${GREEN}health${NC}    - Run health checks"
    echo -e "  ${GREEN}validate${NC}  - Validate configuration"
    echo -e "  ${GREEN}help${NC}      - Show this help message"
    echo ""
    echo -e "${YELLOW}Environments:${NC}"
    echo -e "  ${GREEN}local${NC}       - Local development (default)"
    echo -e "  ${GREEN}development${NC} - Development environment"
    echo -e "  ${GREEN}staging${NC}     - Staging environment"
    echo -e "  ${GREEN}production${NC}  - Production environment"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0 start"
    echo "  $0 status local"
    echo "  $0 logs development"
    echo "  $0 reset local"
    echo ""
    echo -e "${YELLOW}URLs:${NC}"
    echo -e "  ${GREEN}Web UI:${NC} http://localhost:3001"
    echo -e "  ${GREEN}API:${NC}    http://localhost:3001/api"
    echo -e "  ${GREEN}Health:${NC} http://localhost:3001/api/public/health"
}

# Command functions
cmd_start() {
    echo -e "${BLUE}🚀 Starting Langfuse...${NC}"
    "$SCRIPT_DIR/scripts/start-langfuse.sh" "$1"
}

cmd_stop() {
    echo -e "${BLUE}🛑 Stopping Langfuse...${NC}"
    "$SCRIPT_DIR/scripts/stop-langfuse.sh" "$1"
}

cmd_status() {
    "$SCRIPT_DIR/scripts/status-langfuse.sh" "$1"
}

cmd_restart() {
    echo -e "${BLUE}🔄 Restarting Langfuse...${NC}"
    cmd_stop "$1"
    sleep 2
    cmd_start "$1"
}

cmd_logs() {
    local env=${1:-$DEFAULT_ENV}
    echo -e "${BLUE}📋 Viewing Langfuse logs (environment: $env)${NC}"
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
    cd "$(dirname "$SCRIPT_DIR")"
    APP_ENV=$env docker-compose --env-file ".env.$env" logs -f langfuse
}

cmd_reset() {
    "$SCRIPT_DIR/scripts/reset-langfuse.sh" "$1"
}

cmd_init() {
    echo -e "${BLUE}🔧 Initializing Langfuse database...${NC}"
    "$SCRIPT_DIR/scripts/init-langfuse-db.sh" "$1"
}

cmd_health() {
    echo -e "${BLUE}🏥 Running health checks...${NC}"
    "$SCRIPT_DIR/scripts/healthcheck.sh"
}

cmd_validate() {
    echo -e "${BLUE}🔍 Validating configuration...${NC}"
    "$SCRIPT_DIR/scripts/validate-config.sh" "$1"
}

# Main logic
COMMAND=${1:-help}
ENV=${2:-$DEFAULT_ENV}

case $COMMAND in
    "start")
        cmd_start "$ENV"
        ;;
    "stop")
        cmd_stop "$ENV"
        ;;
    "status")
        cmd_status "$ENV"
        ;;
    "restart")
        cmd_restart "$ENV"
        ;;
    "logs")
        cmd_logs "$ENV"
        ;;
    "reset")
        cmd_reset "$ENV"
        ;;
    "init")
        cmd_init "$ENV"
        ;;
    "health")
        cmd_health
        ;;
    "validate")
        cmd_validate "$ENV"
        ;;
    "help"|"--help"|"-h"|"")
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo -e "Use ${YELLOW}$0 help${NC} to see available commands"
        exit 1
        ;;
esac