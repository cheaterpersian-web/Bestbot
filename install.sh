#!/bin/bash

# VPN Telegram Bot - One Script Installer
# نصب کننده یک اسکریپتی ربات تلگرام VPN
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
    echo "║                    VPN Telegram Bot                          ║"
    echo "║                 نصب کننده ربات تلگرام VPN                   ║"
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
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root. This is not recommended for security reasons."
        read -p "Do you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Please run this script as a regular user with sudo privileges."
            exit 1
        fi
    fi
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_success "Linux system detected"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        log_success "macOS system detected"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        log_info "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    # Check if Git is installed
    if ! command -v git &> /dev/null; then
        log_error "Git is not installed. Please install Git first."
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi
    
    log_success "All requirements satisfied"
}

# Install Docker and Docker Compose if not present
install_docker() {
    log_info "Installing Docker and Docker Compose..."
    
    # Update package index
    sudo apt-get update
    
    # Install required packages
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Set up the stable repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    
    # Install Docker Compose
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    
    log_success "Docker and Docker Compose installed successfully"
    log_warning "Please log out and log back in for Docker group changes to take effect"
}

# Clone repository
clone_repository() {
    log_info "Cloning VPN Telegram Bot repository..."
    
    if [ -d "Bestbot" ]; then
        log_warning "Directory 'Bestbot' already exists"
        read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf Bestbot
        else
            log_info "Using existing installation"
            cd Bestbot
            return
        fi
    fi
    
    git clone https://github.com/cheaterpersian-web/Bestbot.git
    cd Bestbot
    
    log_success "Repository cloned successfully"
}

# Create environment file
create_env_file() {
    log_info "Creating environment configuration file..."
    
    if [ -f ".env" ]; then
        log_warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Using existing .env file"
            return
        fi
    fi
    
    # Get user input for configuration
    echo -e "${PURPLE}Please provide the following configuration details:${NC}"
    echo
    
    # Bot Token
    read -p "Enter your Telegram Bot Token (from @BotFather): " BOT_TOKEN
    if [ -z "$BOT_TOKEN" ]; then
        log_error "Bot token is required"
        exit 1
    fi
    
    # Admin IDs
    read -p "Enter Admin IDs (comma-separated, e.g., 123456789,987654321): " ADMIN_IDS
    if [ -z "$ADMIN_IDS" ]; then
        log_error "Admin IDs are required"
        exit 1
    fi
    
    # Bot Username
    read -p "Enter Bot Username (without @): " BOT_USERNAME
    if [ -z "$BOT_USERNAME" ]; then
        log_error "Bot username is required"
        exit 1
    fi
    
    # Database password
    read -s -p "Enter MySQL root password: " MYSQL_ROOT_PASSWORD
    echo
    if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
        MYSQL_ROOT_PASSWORD="vpn_root_$(date +%s)"
        log_warning "Using generated password: $MYSQL_ROOT_PASSWORD"
    fi
    
    # Generate random passwords
    MYSQL_PASSWORD="vpn_pass_$(date +%s)"
    MYSQL_DATABASE="vpn_bot"
    MYSQL_USER="vpn_user"
    
    # Create .env file
    cat > .env << EOF
# Telegram Bot Configuration
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=[$ADMIN_IDS]
BOT_USERNAME=$BOT_USERNAME

# Database Configuration
MYSQL_DATABASE=$MYSQL_DATABASE
MYSQL_USER=$MYSQL_USER
MYSQL_PASSWORD=$MYSQL_PASSWORD
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
DATABASE_URL=mysql+aiomysql://$MYSQL_USER:$MYSQL_PASSWORD@db:3306/$MYSQL_DATABASE?charset=utf8mb4

# Sales Configuration
SALES_ENABLED=true
AUTO_APPROVE_RECEIPTS=false
MIN_TOPUP_AMOUNT=50000
MAX_TOPUP_AMOUNT=50000000

# Security Configuration
ENABLE_FRAUD_DETECTION=true
MAX_DAILY_TRANSACTIONS=10
MAX_DAILY_AMOUNT=1000000

# Referral System
REFERRAL_PERCENT=10
REFERRAL_FIXED=0

# Payment Gateways
ENABLE_STARS=false
ENABLE_ZARINPAL=false
ZARINPAL_MERCHANT_ID=

# Miscellaneous
STATUS_URL=https://your-status-page.com
UPTIME_ROBOT_API_KEY=
SUPPORT_CHANNEL=@your_support_channel

# Redis Configuration
REDIS_URL=redis://redis:6379/0
EOF
    
    log_success "Environment file created successfully"
    log_info "You can edit .env file later to modify settings"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p nginx/ssl
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/grafana/datasources
    mkdir -p logs
    
    log_success "Directories created successfully"
}

# Create nginx configuration
create_nginx_config() {
    log_info "Creating Nginx configuration..."
    
    cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }
    
    server {
        listen 80;
        server_name _;
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /health {
            proxy_pass http://api/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
EOF
    
    log_success "Nginx configuration created"
}

# Create monitoring configurations
create_monitoring_configs() {
    log_info "Creating monitoring configurations..."
    
    # Prometheus configuration
    cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'vpn-bot-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'vpn-bot-bot'
    static_configs:
      - targets: ['bot:8001']
    metrics_path: '/metrics'
    scrape_interval: 30s
EOF
    
    # Grafana datasource
    cat > monitoring/grafana/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF
    
    log_success "Monitoring configurations created"
}

# Build and start services
start_services() {
    log_info "Building and starting services..."
    
    # Pull latest images
    docker-compose pull
    
    # Build custom images
    docker-compose build
    
    # Start services
    docker-compose up -d
    
    log_success "Services started successfully"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for database
    log_info "Waiting for database..."
    timeout 60 bash -c 'until docker-compose exec -T db mysqladmin ping -h localhost --silent; do sleep 2; done'
    
    # Wait for Redis
    log_info "Waiting for Redis..."
    timeout 30 bash -c 'until docker-compose exec -T redis redis-cli ping; do sleep 2; done'
    
    # Wait for API
    log_info "Waiting for API..."
    timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 5; done'
    
    log_success "All services are ready"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    docker-compose exec -T bot python -m alembic upgrade head
    
    log_success "Database migrations completed"
}

# Show installation summary
show_summary() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Installation Complete!                   ║"
    echo "║                   نصب با موفقیت انجام شد!                   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${CYAN}Service URLs:${NC}"
    echo -e "  • Bot: @$BOT_USERNAME"
    echo -e "  • API: http://localhost:8000"
    echo -e "  • Grafana: http://localhost:3000 (admin/admin)"
    echo -e "  • Prometheus: http://localhost:9090"
    echo
    echo -e "${CYAN}Useful Commands:${NC}"
    echo -e "  • View logs: ${YELLOW}docker-compose logs -f${NC}"
    echo -e "  • Stop services: ${YELLOW}docker-compose down${NC}"
    echo -e "  • Restart services: ${YELLOW}docker-compose restart${NC}"
    echo -e "  • Update bot: ${YELLOW}git pull && docker-compose up -d --build${NC}"
    echo
    echo -e "${CYAN}Configuration:${NC}"
    echo -e "  • Edit settings: ${YELLOW}nano .env${NC}"
    echo -e "  • Database password: ${YELLOW}$MYSQL_PASSWORD${NC}"
    echo
    echo -e "${GREEN}Your VPN Telegram Bot is now running!${NC}"
    echo -e "${GREEN}ربات تلگرام VPN شما اکنون در حال اجرا است!${NC}"
}

# Main installation function
main() {
    print_banner
    
    log_info "Starting VPN Telegram Bot installation..."
    echo
    
    # Check if user wants to install Docker
    if ! command -v docker &> /dev/null; then
        log_warning "Docker is not installed"
        read -p "Do you want to install Docker automatically? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_docker
        else
            log_error "Docker is required to continue"
            exit 1
        fi
    fi
    
    check_requirements
    clone_repository
    create_env_file
    create_directories
    create_nginx_config
    create_monitoring_configs
    start_services
    wait_for_services
    run_migrations
    show_summary
}

# Run main function
main "$@"