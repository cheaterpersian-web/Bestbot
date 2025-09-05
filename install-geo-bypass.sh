#!/bin/bash

# VPN Telegram Bot - Geographic Bypass Installer
# نصب کننده ربات تلگرام VPN با دور زدن محدودیت‌های جغرافیایی
# Author: VPN Bot Team
# Version: 1.0.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              VPN Telegram Bot - Geo Bypass                  ║"
    echo "║         نصب کننده ربات تلگرام VPN - دور زدن محدودیت        ║"
    echo "║                                                              ║"
    echo "║  Version: 1.0.0                                              ║"
    echo "║  Author: VPN Bot Team                                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

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

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Configure Docker to use alternative registries
configure_docker_registries() {
    log_info "Configuring Docker to use alternative registries..."
    
    # Create or update Docker daemon configuration
    mkdir -p /etc/docker
    
    cat > /etc/docker/daemon.json << EOF
{
    "registry-mirrors": [
        "https://docker.mirror.iranrepo.ir",
        "https://docker.iranrepo.ir",
        "https://registry.docker-cn.com",
        "https://dockerhub.azk8s.cn",
        "https://reg-mirror.qiniu.com"
    ],
    "insecure-registries": [
        "docker.mirror.iranrepo.ir",
        "docker.iranrepo.ir"
    ]
}
EOF

    log_success "Docker registry configuration updated"
}

# Restart Docker service
restart_docker() {
    log_info "Restarting Docker service..."
    systemctl restart docker
    sleep 5
    log_success "Docker service restarted"
}

# Try to pull images with different strategies
pull_images_with_fallback() {
    log_info "Attempting to pull Docker images with fallback strategies..."
    
    # List of images to pull
    declare -A images=(
        ["mysql:8.3"]="mysql:8.3"
        ["redis:7-alpine"]="redis:7-alpine"
        ["nginx:alpine"]="nginx:alpine"
        ["prom/prometheus:latest"]="quay.io/prometheus/prometheus:latest"
        ["grafana/grafana:latest"]="quay.io/grafana/grafana:latest"
    )
    
    for original_image in "${!images[@]}"; do
        alternative_image="${images[$original_image]}"
        
        log_info "Trying to pull: $original_image"
        
        # Try original image first
        if docker pull "$original_image" 2>/dev/null; then
            log_success "Successfully pulled: $original_image"
            continue
        fi
        
        # Try alternative registry
        log_warning "Failed to pull $original_image, trying alternative: $alternative_image"
        if docker pull "$alternative_image" 2>/dev/null; then
            log_success "Successfully pulled alternative: $alternative_image"
            # Tag the alternative image with the original name
            docker tag "$alternative_image" "$original_image"
        else
            log_error "Failed to pull both $original_image and $alternative_image"
        fi
    done
}

# Install without monitoring (minimal setup)
install_minimal() {
    log_info "Installing minimal setup without monitoring components..."
    
    if [[ -f "docker-compose-minimal.yml" ]]; then
        docker-compose -f docker-compose-minimal.yml up -d
        log_success "Minimal setup completed successfully"
    else
        log_error "docker-compose-minimal.yml not found"
        exit 1
    fi
}

# Install with alternative monitoring
install_with_alternative_monitoring() {
    log_info "Installing with alternative monitoring setup..."
    
    if [[ -f "docker-compose-alternative.yml" ]]; then
        docker-compose -f docker-compose-alternative.yml up -d
        log_success "Alternative setup with monitoring completed successfully"
    else
        log_error "docker-compose-alternative.yml not found"
        exit 1
    fi
}

# Main installation function
main() {
    print_banner
    
    log_info "Starting VPN Bot installation with geographic bypass..."
    
    # Check if running as root
    check_root
    
    # Configure Docker registries
    configure_docker_registries
    
    # Restart Docker
    restart_docker
    
    # Try to pull images
    pull_images_with_fallback
    
    # Ask user for installation type
    echo -e "${YELLOW}Choose installation type:${NC}"
    echo "1) Minimal setup (without monitoring)"
    echo "2) Full setup with alternative monitoring"
    echo "3) Exit"
    
    read -p "Enter your choice (1-3): " choice
    
    case $choice in
        1)
            install_minimal
            ;;
        2)
            install_with_alternative_monitoring
            ;;
        3)
            log_info "Installation cancelled by user"
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
    
    log_success "Installation completed successfully!"
    log_info "You can now access your VPN Bot at:"
    log_info "- API: http://localhost:8000"
    log_info "- Bot: Running in background"
    
    if [[ $choice -eq 2 ]]; then
        log_info "- Prometheus: http://localhost:9090"
        log_info "- Grafana: http://localhost:3000 (admin/admin)"
    fi
}

# Run main function
main "$@"