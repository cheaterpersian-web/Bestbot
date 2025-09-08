#!/bin/bash

# VPN Telegram Bot - Update Script
# اسکریپت به روزرسانی ربات تلگرام VPN

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
BACKUP_BEFORE_UPDATE=true
STOP_SERVICES=true
PULL_CHANGES=true
REBUILD_IMAGES=true
RUN_MIGRATIONS=true

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
print_banner() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                VPN Telegram Bot Updater                     ║"
    echo "║              به روزرسان ربات تلگرام VPN                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if we're in the right directory
check_directory() {
    if [ ! -f "docker-compose.yml" ] || [ ! -f ".env" ]; then
        log_error "This script must be run from the VPN Telegram Bot root directory"
        log_error "Please navigate to the project directory and run this script again"
        exit 1
    fi
    log_success "Running in correct directory"
}

# Check if services are running
check_services() {
    log_info "Checking current service status..."
    
    if docker compose ps | grep -q "Up"; then
        log_info "Services are currently running"
        return 0
    else
        log_info "Services are not running"
        return 1
    fi
}

# Create backup before update
create_backup() {
    if [ "$BACKUP_BEFORE_UPDATE" = true ]; then
        log_info "Creating backup before update..."
        
        if [ -f "scripts/backup.sh" ]; then
            chmod +x scripts/backup.sh
            ./scripts/backup.sh
            log_success "Backup created successfully"
        else
            log_warning "Backup script not found, skipping backup"
        fi
    fi
}

# Stop services
stop_services() {
    if [ "$STOP_SERVICES" = true ]; then
        log_info "Stopping services..."
        docker compose down
        log_success "Services stopped"
    fi
}

# Pull latest changes
pull_changes() {
    if [ "$PULL_CHANGES" = true ]; then
        log_info "Pulling latest changes from repository..."
        
        # Check if we're in a git repository
        if [ -d ".git" ]; then
            # Stash any local changes
            if ! git diff --quiet; then
                log_warning "Local changes detected, stashing them..."
                git stash push -m "Auto-stash before update $(date)"
            fi
            
            # Pull latest changes
            git pull origin main
            
            if [ $? -eq 0 ]; then
                log_success "Latest changes pulled successfully"
            else
                log_error "Failed to pull changes"
                exit 1
            fi
        else
            log_warning "Not a git repository, skipping git pull"
        fi
    fi
}

# Update Docker images
update_images() {
    log_info "Updating Docker images..."
    
    # Pull latest base images
    docker compose pull
    
    if [ "$REBUILD_IMAGES" = true ]; then
        log_info "Rebuilding custom images..."
        docker compose build --no-cache
    fi
    
    log_success "Docker images updated"
}

# Start services
start_services() {
    log_info "Starting services..."
    docker compose up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    # Check if services are running
    if docker compose ps | grep -q "Up"; then
        log_success "Services started successfully"
    else
        log_error "Failed to start services"
        docker compose logs | cat
        exit 1
    fi
}

# Run database migrations
run_migrations() {
    if [ "$RUN_MIGRATIONS" = true ]; then
        log_info "Running database migrations..."
        
        # Wait for database to be ready (MySQL)
        log_info "Waiting for database to be ready (MySQL)..."
        timeout 60 bash -c 'until docker compose exec -T db sh -lc "mysqladmin ping -h localhost -u${MYSQL_USER:-vpn_user} -p${MYSQL_PASSWORD:-vpn_pass}"; do sleep 2; done'
        
        # Run migrations
        docker compose exec -T api alembic upgrade head
        
        if [ $? -eq 0 ]; then
            log_success "Database migrations completed"
        else
            log_error "Database migrations failed"
            exit 1
        fi
    fi
}

# Verify update
verify_update() {
    log_info "Verifying update..."
    
    # Check API health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "API is responding"
    else
        log_warning "API health check failed"
    fi
    
    # Check bot status
    if docker compose exec -T bot python -c "import requests; requests.get('https://api.telegram.org/bot\${BOT_TOKEN}/getMe')" > /dev/null 2>&1; then
        log_success "Bot is responding"
    else
        log_warning "Bot status check failed"
    fi
    
    # Show service status
    log_info "Current service status:"
    docker compose ps
}

# Show update summary
show_summary() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Update Complete!                         ║"
    echo "║                   به روزرسانی تکمیل شد!                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${CYAN}Service URLs:${NC}"
    echo -e "  • API: http://localhost:8000"
    echo -e "  • Grafana: http://localhost:3000"
    echo -e "  • Prometheus: http://localhost:9090"
    echo
    echo -e "${CYAN}Useful Commands:${NC}"
    echo -e "  • View logs: ${YELLOW}docker compose logs -f | cat${NC}"
    echo -e "  • Check status: ${YELLOW}docker compose ps${NC}"
    echo -e "  • Restart services: ${YELLOW}docker compose restart${NC}"
    echo
    echo -e "${GREEN}Your VPN Telegram Bot has been updated successfully!${NC}"
    echo -e "${GREEN}ربات تلگرام VPN شما با موفقیت به روزرسانی شد!${NC}"
}

# Handle errors
handle_error() {
    log_error "Update failed at step: $1"
    log_info "Attempting to restore services..."
    
    # Try to start services
    docker compose up -d
    
    log_warning "Please check the logs and try again:"
    log_warning "docker compose logs | cat"
    
    exit 1
}

# Main update function
main() {
    print_banner
    
    log_info "Starting VPN Telegram Bot update process..."
    echo
    
    # Set error trap
    trap 'handle_error "unknown"' ERR
    
    check_directory
    
    if check_services; then
        create_backup
        stop_services
    fi
    
    pull_changes
    update_images
    start_services
    run_migrations
    verify_update
    show_summary
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-backup)
            BACKUP_BEFORE_UPDATE=false
            shift
            ;;
        --no-stop)
            STOP_SERVICES=false
            shift
            ;;
        --no-pull)
            PULL_CHANGES=false
            shift
            ;;
        --no-rebuild)
            REBUILD_IMAGES=false
            shift
            ;;
        --no-migrations)
            RUN_MIGRATIONS=false
            shift
            ;;
        --help)
            echo "VPN Telegram Bot Update Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-backup      Skip backup before update"
            echo "  --no-stop        Don't stop services before update"
            echo "  --no-pull        Don't pull git changes"
            echo "  --no-rebuild     Don't rebuild Docker images"
            echo "  --no-migrations  Don't run database migrations"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"