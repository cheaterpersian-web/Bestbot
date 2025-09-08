#!/bin/bash

# VPN Telegram Bot - Backup Script
# اسکریپت پشتیبان گیری ربات تلگرام VPN

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
MAX_BACKUPS=7

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

# Create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log_info "Created backup directory: $BACKUP_DIR"
    fi
}

# Backup database
backup_database() {
    log_info "Starting database backup..."
    
    local db_backup_file="$BACKUP_DIR/database_$DATE.sql"
    
    # Get database credentials from .env file
    if [ -f ".env" ]; then
        source .env
    else
        log_error ".env file not found"
        exit 1
    fi
    
    # Create database backup (MySQL)
    : "${MYSQL_DATABASE:=vpn_bot}"
    : "${MYSQL_USER:=vpn_user}"
    : "${MYSQL_PASSWORD:=vpn_pass}"
    docker compose exec -T db sh -lc "mysqldump -u$MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE" > "$db_backup_file"
    
    if [ $? -eq 0 ]; then
        log_success "Database backup created: $db_backup_file"
        
        # Compress the backup
        gzip "$db_backup_file"
        log_success "Database backup compressed: $db_backup_file.gz"
    else
        log_error "Database backup failed"
        exit 1
    fi
}

# Backup configuration files
backup_config() {
    log_info "Starting configuration backup..."
    
    local config_backup_file="$BACKUP_DIR/config_$DATE.tar.gz"
    
    # Create configuration backup
    tar -czf "$config_backup_file" \
        .env \
        docker-compose.yml \
        nginx/ \
        monitoring/ \
        scripts/ \
        --exclude="*.log" \
        --exclude="*.tmp" \
        2>/dev/null
    
    if [ $? -eq 0 ]; then
        log_success "Configuration backup created: $config_backup_file"
    else
        log_error "Configuration backup failed"
        exit 1
    fi
}

# Backup logs
backup_logs() {
    log_info "Starting logs backup..."
    
    local logs_backup_file="$BACKUP_DIR/logs_$DATE.tar.gz"
    
    # Create logs backup
    if [ -d "logs" ]; then
        tar -czf "$logs_backup_file" logs/ 2>/dev/null
        if [ $? -eq 0 ]; then
            log_success "Logs backup created: $logs_backup_file"
        else
            log_warning "Logs backup failed (no logs directory found)"
        fi
    else
        log_warning "No logs directory found, skipping logs backup"
    fi
}

# Clean old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last $MAX_BACKUPS)..."
    
    # Count total backup files
    local total_backups=$(find "$BACKUP_DIR" -name "*.gz" -type f | wc -l)
    
    if [ "$total_backups" -gt "$MAX_BACKUPS" ]; then
        # Remove oldest backups
        find "$BACKUP_DIR" -name "*.gz" -type f -printf '%T@ %p\n' | \
        sort -n | \
        head -n $((total_backups - MAX_BACKUPS)) | \
        cut -d' ' -f2- | \
        xargs rm -f
        
        log_success "Cleaned up old backups"
    else
        log_info "No cleanup needed (current backups: $total_backups)"
    fi
}

# Create backup summary
create_summary() {
    local summary_file="$BACKUP_DIR/backup_summary_$DATE.txt"
    
    cat > "$summary_file" << EOF
VPN Telegram Bot Backup Summary
===============================
Date: $(date)
Backup ID: $DATE

Files Created:
$(find "$BACKUP_DIR" -name "*$DATE*" -type f -exec ls -lh {} \;)

Total Backup Size:
$(du -sh "$BACKUP_DIR" | cut -f1)

Database Status:
$(docker compose exec -T db sh -lc "mysql -u$MYSQL_USER -p$MYSQL_PASSWORD -e 'SHOW TABLES FROM $MYSQL_DATABASE;'" 2>/dev/null || echo "Database check failed")

Services Status:
$(docker compose ps)

EOF
    
    log_success "Backup summary created: $summary_file"
}

# Send notification (if configured)
send_notification() {
    if [ -n "$BACKUP_NOTIFICATION_URL" ]; then
        log_info "Sending backup notification..."
        
        local message="VPN Bot Backup Completed Successfully\nDate: $(date)\nBackup ID: $DATE"
        
        curl -s -X POST "$BACKUP_NOTIFICATION_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"$message\"}" > /dev/null
        
        if [ $? -eq 0 ]; then
            log_success "Notification sent"
        else
            log_warning "Failed to send notification"
        fi
    fi
}

# Main backup function
main() {
    log_info "Starting VPN Telegram Bot backup process..."
    log_info "Backup ID: $DATE"
    
    create_backup_dir
    backup_database
    backup_config
    backup_logs
    cleanup_old_backups
    create_summary
    send_notification
    
    log_success "Backup process completed successfully!"
    log_info "Backup location: $BACKUP_DIR"
    
    # Show backup size
    local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    log_info "Total backup size: $total_size"
}

# Run main function
main "$@"