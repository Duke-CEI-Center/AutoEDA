#!/bin/bash

# =============================================================================
# MCP-EDA Docker Deployment Script
# =============================================================================
# This script helps deploy the MCP-EDA platform using Docker Compose
# Usage: ./docker/deploy.sh [command] [options]

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default configuration
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$SCRIPT_DIR/env.docker.example"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  MCP-EDA Docker Deployment${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_warning "Environment file not found: $ENV_FILE"
        
        if [ -f "$ENV_EXAMPLE" ]; then
            print_info "Copying example environment file..."
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            print_warning "Please edit $ENV_FILE with your configuration before continuing"
            print_info "Required: Set your OPENAI_API_KEY and EDA tool paths"
            exit 1
        else
            print_error "No environment example file found: $ENV_EXAMPLE"
            exit 1
        fi
    fi
    
    # Check for required environment variables
    source "$ENV_FILE"
    
    if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
        print_error "OPENAI_API_KEY is not set in $ENV_FILE"
        exit 1
    fi
    
    print_success "Environment file is configured"
}

build_images() {
    print_info "Building Docker images..."
    cd "$PROJECT_ROOT"
    
    docker-compose build --no-cache
    print_success "Docker images built successfully"
}

start_services() {
    print_info "Starting MCP-EDA services..."
    cd "$PROJECT_ROOT"
    
    # Start core services
    docker-compose up -d eda-servers mcp-agent-client
    
    print_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    if docker-compose ps | grep -q "unhealthy"; then
        print_warning "Some services may not be healthy. Checking logs..."
        docker-compose logs --tail=20
    else
        print_success "All services are running"
    fi
    
    print_info "Service URLs:"
    echo "  - Agent Client: http://localhost:8000"
    echo "  - Agent Docs: http://localhost:8000/docs"
    echo "  - Synthesis Server: http://localhost:13333/docs"
    echo "  - Unified Placement Server: http://localhost:13340/docs"
    echo "  - CTS Server: http://localhost:13338/docs"
    echo "  - Unified Route Save Server: http://localhost:13341/docs"
}

stop_services() {
    print_info "Stopping MCP-EDA services..."
    cd "$PROJECT_ROOT"
    
    docker-compose down
    print_success "Services stopped"
}

restart_services() {
    print_info "Restarting MCP-EDA services..."
    stop_services
    start_services
}

show_logs() {
    cd "$PROJECT_ROOT"
    if [ -n "$2" ]; then
        docker-compose logs -f "$2"
    else
        docker-compose logs -f
    fi
}

show_status() {
    print_info "Service status:"
    cd "$PROJECT_ROOT"
    docker-compose ps
    
    print_info "Health check:"
    docker-compose exec eda-servers python3 health_check.py 2>/dev/null || print_warning "Health check failed or services not running"
}

run_tests() {
    print_info "Running tests..."
    cd "$PROJECT_ROOT"
    
    docker-compose --profile test run --rm test-runner
}

run_experiment() {
    print_info "Running experiment..."
    cd "$PROJECT_ROOT"
    
    if [ -n "$2" ]; then
        docker-compose --profile experiment run --rm experiment-runner "$2"
    else
        docker-compose --profile experiment run --rm experiment-runner
    fi
}

cleanup() {
    print_info "Cleaning up Docker resources..."
    cd "$PROJECT_ROOT"
    
    docker-compose down -v --remove-orphans
    docker system prune -f
    print_success "Cleanup completed"
}

show_help() {
    echo "MCP-EDA Docker Deployment Script"
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  build         Build Docker images"
    echo "  start         Start all services"
    echo "  stop          Stop all services"
    echo "  restart       Restart all services"
    echo "  status        Show service status"
    echo "  logs [service] Show logs (optionally for specific service)"
    echo "  test          Run test suite"
    echo "  experiment [cmd] Run experiment (optionally with specific command)"
    echo "  cleanup       Clean up Docker resources"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build                    # Build all images"
    echo "  $0 start                    # Start all services"
    echo "  $0 logs eda-servers         # Show EDA servers logs"
    echo "  $0 test                     # Run all tests"
    echo "  $0 experiment --help        # Show experiment options"
    echo ""
    echo "Environment:"
    echo "  Copy docker/env.docker.example to .env and configure your settings"
    echo "  Required: OPENAI_API_KEY, EDA tool paths, license servers"
}

# =============================================================================
# Main Script Logic
# =============================================================================

main() {
    print_header
    
    case "${1:-help}" in
        "build")
            check_dependencies
            check_env_file
            build_images
            ;;
        "start")
            check_dependencies
            check_env_file
            start_services
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            check_dependencies
            check_env_file
            restart_services
            ;;
        "status")
            show_status
            ;;
        "logs")
            show_logs "$@"
            ;;
        "test")
            check_dependencies
            check_env_file
            run_tests
            ;;
        "experiment")
            check_dependencies
            check_env_file
            run_experiment "$@"
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"